"""Content-addressed quarantine catalog. No operational database access."""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from app.knowledge.extraction import PIPELINE_VERSION, text_issues
from app.knowledge.models import DocumentAudit, Evidence


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def extract_pdf(path):
    result = subprocess.run(
        [sys.executable, "-m", "app.knowledge.extraction", str(path)],
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise ValueError("pdf_extraction_failed")
    return json.loads(result.stdout)


def identify(pages):
    """Candidates only: mention in a manual is not proof of applicability."""
    patterns = {
        "model": r"\b(?:B10|C10)\b",
        "powertrain": r"\b(?:BEV|REEV)\b",
        "model_year": r"\b20(?:26|27)\b",
        "manufacturer": r"\bLeapmotor\b",
    }
    candidates, evidence = {}, []
    for field, pattern in patterns.items():
        matches = []
        for page in pages:
            # Cover/preface candidates, never filesystem filename inference.
            if page["page"] > 10:
                break
            for text in [page["text"], page["alternate_text"]]:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    value = match[0].upper() if field in {"model", "powertrain"} else match[0]
                    if value not in matches:
                        matches.append(value)
                        evidence.append(
                            Evidence(
                                field=field,
                                value=value,
                                page=page["page"],
                                quote=text[max(0, match.start() - 60) : match.end() + 60],
                            )
                        )
        if matches:
            candidates[field] = matches
    return candidates, evidence


def catalog_files(files, output, *, extractor=extract_pdf, metadata_reviews=()):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    documents, errors = {}, []
    reviews = {r.sha256: r for r in metadata_reviews}
    if len(reviews) != len(metadata_reviews):
        raise ValueError("Multiple metadata reviews for the same document")
    for file in sorted(map(Path, files), key=str):
        try:
            if not file.is_file() or file.stat().st_size > 80_000_000:
                raise ValueError("missing_file_or_size_limit")
            with file.open("rb") as stream:
                if stream.read(5) != b"%PDF-":
                    raise ValueError("invalid_pdf_signature")
            data = file.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in documents:
                documents[digest].files.append(file.name)
                continue
            archive = output / "originals" / (digest + ".pdf")
            archive.parent.mkdir(exist_ok=True, mode=0o700)
            if archive.exists():
                if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
                    raise ValueError("archive_integrity_mismatch")
            else:
                fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
            cache = output / "extractions" / (digest + ".json")
            if cache.exists():
                raw = json.loads(cache.read_text())
                if raw.get("sha256") != digest or raw.get("pipeline_version") != PIPELINE_VERSION:
                    raw = {}
            else:
                raw = {}
            if not raw:
                raw = {**extractor(archive), "sha256": digest, "pipeline_version": PIPELINE_VERSION}
                atomic_json(cache, raw)
            for page in raw["pages"]:
                retained = [
                    i
                    for i in page["issues"]
                    if i
                    in {
                        "primary_extraction_failed",
                        "alternate_extraction_failed",
                        "extractors_disagree",
                        "page_text_truncated",
                    }
                ]
                page["issues"] = sorted(
                    set(retained + text_issues(page["text"]) + text_issues(page["alternate_text"]))
                )
                left, right = len(page["text"]), len(page["alternate_text"])
                page["quality_metrics"] = {
                    "primary_characters": left,
                    "alternate_characters": right,
                    "length_agreement": min(left, right) / max(left, right)
                    if max(left, right)
                    else 0,
                }
            # Quality rules may evolve without rerunning PDF parsers or OCR.
            atomic_json(cache, raw)
            candidates, evidence = identify(raw["pages"])
            issues = sorted({issue for p in raw["pages"] for issue in p["issues"]})
            record = DocumentAudit(
                document_id="doc-" + digest,
                sha256=digest,
                files=[file.name],
                size_bytes=len(data),
                page_count=len(raw["pages"]),
                pdf_metadata=raw["pdf_metadata"],
                candidates=candidates,
                evidence=evidence,
                issues=issues,
                pages=raw["pages"],
                pipeline_version=PIPELINE_VERSION,
                extractor_versions=raw["extractor_versions"],
                extraction_status="review_required" if issues else "extracted_unreviewed",
            )
            if digest in reviews:
                record = apply_metadata_review(record, reviews[digest])
            documents[digest] = record
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            known = {
                "missing_file_or_size_limit",
                "invalid_pdf_signature",
                "archive_integrity_mismatch",
                "pdf_extraction_failed",
            }
            reason = str(exc) if str(exc) in known else "document_processing_failed"
            if isinstance(exc, subprocess.TimeoutExpired):
                reason = "extraction_timeout"
            errors.append({"file": file.name, "error": reason})
    records = list(documents.values())
    report = {
        "checkpoint": "A",
        "status": "review_required" if records else "blocked",
        "input_files": len(files),
        "unique_documents": len(records),
        "duplicate_files": sum(len(d.files) - 1 for d in records),
        "expected_unique_documents": 6,
        "errors": errors,
        "total_pages": sum(d.page_count for d in records),
        "page_issue_counts": dict(Counter(i for d in records for p in d.pages for i in p.issues)),
        "approved_documents": 0,
        "active_chunks": 0,
        "identity_validation": "pending_visual_and_semantic_review",
        "documents": [d.model_dump(exclude={"pages"}) for d in records],
    }
    atomic_json(output / "catalog.json", report)
    return report


def apply_metadata_review(record, review):
    """Bind every explicit metadata decision to a page of this exact PDF."""
    if record.sha256 != review.sha256:
        raise ValueError("Metadata review hash does not match original")
    updates = {}
    for evidence in review.evidence:
        if evidence.page > record.page_count:
            raise ValueError("Metadata evidence page outside document")
        page = record.pages[evidence.page - 1]
        if evidence.basis == "internal_text" and not any(
            evidence.quote in text for text in (page.text, page.alternate_text)
        ):
            raise ValueError("Metadata evidence quote not found on page")
        value = int(evidence.value) if evidence.field == "model_year" else evidence.value
        if evidence.field in updates and updates[evidence.field] != value:
            raise ValueError("Conflicting metadata evidence")
        updates[evidence.field] = value
    # Revalidate canonical literals; metadata review cannot change approval.
    return DocumentAudit.model_validate(
        {
            **record.model_dump(),
            **updates,
            "evidence": [e.model_dump() for e in review.evidence],
            "metadata_reviewed_by": review.reviewed_by,
        }
    )
