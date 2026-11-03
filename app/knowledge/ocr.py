"""Explicit page-only local OCR, cached by original, engine and language data."""

import csv
import hashlib
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path

from app.knowledge.catalog import atomic_json
from app.knowledge.recovery import digest_text, page_metrics


def tsv_text(raw):
    lines, scores = {}, []
    for row in csv.DictReader(io.StringIO(raw), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        key = tuple(row[n] for n in ("page_num", "block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(row["text"])
        try:
            scores.append(float(row["conf"]))
        except ValueError:
            pass
    return "\n".join(" ".join(words) for words in lines.values()), scores


def ocr_page(
    pdf_path,
    original_hash,
    page_number,
    output,
    *,
    binary,
    tessdata,
    libraries=None,
    dpi=200,
    timeout=60,
):
    import pymupdf

    if dpi < 100 or dpi > 300:
        raise ValueError("OCR dpi must be 100..300")
    pdf_path, binary, tessdata, output = map(Path, (pdf_path, binary, tessdata, output))
    if hashlib.sha256(pdf_path.read_bytes()).hexdigest() != original_hash:
        raise ValueError("Original PDF integrity mismatch")
    language = tessdata / "por.traineddata"
    config = {
        "document_sha256": original_hash,
        "page": page_number,
        "dpi": dpi,
        "engine_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "language_sha256": hashlib.sha256(language.read_bytes()).hexdigest(),
        "language": "por",
        "psm": 3,
        "strategy": "selective-ocr-v1",
    }
    key = digest_text(json.dumps(config, sort_keys=True))
    destination = output / "ocr" / (key + ".json")
    if destination.exists():
        cached = json.loads(destination.read_text())
        if cached.get("config") == config and digest_text(cached["text"]) == cached["text_sha256"]:
            return cached
        raise ValueError("OCR cache integrity mismatch")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {**os.environ, "TESSDATA_PREFIX": str(tessdata.resolve()), "OMP_THREAD_LIMIT": "1"}
    if libraries:
        env["LD_LIBRARY_PATH"] = str(Path(libraries).resolve())
    with pymupdf.open(pdf_path) as document:
        if not 1 <= page_number <= len(document):
            raise ValueError("OCR page outside document")
        page = document[page_number - 1]
        pixels = page.rect.width * page.rect.height * (dpi / 72) ** 2
        if pixels > 20_000_000:
            raise ValueError("OCR pixel limit exceeded")
        with tempfile.TemporaryDirectory(dir=output) as temp:
            image = Path(temp) / "page.png"
            page.get_pixmap(dpi=dpi).save(image)
            result = subprocess.run(
                [str(binary.resolve()), str(image), "stdout", "-l", "por", "--psm", "3", "tsv"],
                capture_output=True,
                timeout=timeout,
                env=env,
                check=False,
            )
        if result.returncode:
            raise ValueError("Local OCR engine failed")
        text, confidences = tsv_text(result.stdout.decode())
        if not text.strip():
            raise ValueError("OCR returned empty text")
    record = {
        "config": config,
        "cache_key": key,
        "text": text,
        "text_sha256": digest_text(text),
        "metrics": page_metrics("", text),
        "review_status": "review_required",
        "word_confidence_mean": sum(confidences) / len(confidences) if confidences else None,
        "tsv": result.stdout.decode(),
    }
    atomic_json(destination, record)
    return record
