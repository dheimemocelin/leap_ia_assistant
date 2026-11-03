"""Offline A.1 recovery. Does not publish to the agent or approve sections."""

import argparse
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path

from app.knowledge.catalog import atomic_json
from app.knowledge.recovery import (
    RECOVERY_VERSION,
    derived_document,
    digest_text,
    extract_blocks,
    extract_tables,
    glyph_maps,
    page_metrics,
)


def refresh_quality(artifact, original):
    """Re-evaluate quality from an untouched original without repeating table parsing."""
    if any(digest_text(page["text"]) != page["text_sha256"] for page in artifact["pages"]):
        raise ValueError("Recovered text integrity mismatch")
    mapped = {font["font_xref"] for font in artifact["font_maps"]}
    for page in artifact["pages"]:
        source = original[page["page"] - 1]
        page["metrics"] = page_metrics(source.get_text(sort=True), page["text"])
        missing = [
            entry[0]
            for entry in source.get_fonts(full=True)
            if entry[2] == "Type0"
            and entry[5] == "Identity-H"
            and original.xref_get_key(entry[0], "ToUnicode")[0] == "null"
            and entry[0] not in mapped
        ]
        page["unmapped_identity_fonts"] = missing
        if missing:
            page["metrics"]["after_issues"].append("unmapped_identity_font")
        hard = {
            "encoding_suspect",
            "unexpected_glyphs_or_language",
            "fragmented_words",
            "unmapped_identity_font",
        }
        page["ocr_candidate"] = (
            bool(hard.intersection(page["metrics"]["after_issues"])) or not page["text"].strip()
        )
    pages = artifact["pages"]
    summary = artifact["summary"]
    summary.update(
        {
            "native_text_changed_pages": sum(p["metrics"]["text_changed"] for p in pages),
            "native_encoding_improved_pages": sum(
                p["metrics"]["before_invalid_ratio"] > p["metrics"]["after_invalid_ratio"]
                for p in pages
            ),
            "pages_needing_ocr_or_review": sum(p["ocr_candidate"] for p in pages),
            "before_invalid_ratio": sum(
                p["metrics"]["before_invalid_ratio"] * p["metrics"]["before_characters"]
                for p in pages
            )
            / max(1, sum(p["metrics"]["before_characters"] for p in pages)),
            "after_invalid_ratio": sum(
                p["metrics"]["after_invalid_ratio"] * p["metrics"]["after_characters"]
                for p in pages
            )
            / max(1, sum(p["metrics"]["after_characters"] for p in pages)),
            "remaining_issue_counts": dict(
                Counter(i for p in pages for i in p["metrics"]["after_issues"])
            ),
        }
    )
    summary["quality_version"] = "original-baseline-v2"
    artifact["quality_version"] = "original-baseline-v2"
    return artifact


def recover_all(catalog_root, output, document_hash=None):
    import fontTools
    import pymupdf

    catalog_root, output = Path(catalog_root), Path(output)
    report = json.loads((catalog_root / "catalog.json").read_text())
    if document_hash and document_hash not in {r["sha256"] for r in report["documents"]}:
        raise ValueError("Document SHA-256 not found in catalog")
    references = {}
    # Registry contains font encoding information only, never cross-vehicle facts.
    for record in report["documents"]:
        path = catalog_root / "originals" / (record["sha256"] + ".pdf")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Original integrity mismatch")
        with pymupdf.open(path) as doc:
            for key, value in glyph_maps(doc, record["sha256"]).items():
                if key in references and references[key]["mapping"] != value["mapping"]:
                    raise ValueError("Conflicting reference maps")
                references[key] = value
    reference_fingerprint = digest_text(json.dumps(references, sort_keys=True))
    results = []
    for record in report["documents"]:
        if document_hash and record["sha256"] != document_hash:
            continue
        started = time.monotonic()
        sha = record["sha256"]
        config = {
            "original_sha256": sha,
            "version": RECOVERY_VERSION,
            "reference_fingerprint": reference_fingerprint,
            "pymupdf": pymupdf.VersionBind,
            "fonttools": fontTools.__version__,
            "normalization": "NFC",
            "tables": "ruled-lines-candidates-v1",
        }
        key = digest_text(json.dumps(config, sort_keys=True))
        path = catalog_root / "originals" / (sha + ".pdf")
        destination = output / "documents" / (sha + ".json")
        if destination.exists():
            cached = json.loads(destination.read_text())
            if cached["config"] == config:
                with pymupdf.open(path) as source:
                    cached = refresh_quality(cached, source)
                atomic_json(destination, cached)
                results.append(cached["summary"])
                print(json.dumps({"document": sha[:12], "cache": "hit"}), flush=True)
                continue
        path = catalog_root / "originals" / (sha + ".pdf")
        original = pymupdf.open(path)
        derived, changed = derived_document(original, sha, references)
        pages = []
        for i, page in enumerate(derived):
            before = original[i].get_text(sort=True)
            blocks = extract_blocks(page)
            text = unicodedata.normalize("NFC", page.get_text(sort=True))
            drawings = page.get_drawings()
            line_count = sum(item[0] in {"l", "re"} for d in drawings for item in d["items"])
            tables, failures = [], []
            if line_count >= 8:
                try:
                    tables = extract_tables(page)
                except Exception:  # noqa: BLE001 - keep the page quarantined on geometry/parser failure
                    failures.append("table_extraction_failed")
            metrics = page_metrics(before, text)
            hard_issues = {"encoding_suspect", "unexpected_glyphs_or_language", "fragmented_words"}
            needs_ocr = bool(hard_issues.intersection(metrics["after_issues"])) or not text.strip()
            pages.append(
                {
                    "page": i + 1,
                    "text": text,
                    "text_sha256": digest_text(text),
                    "blocks": blocks,
                    "tables": tables,
                    "metrics": metrics,
                    "failures": failures,
                    "ocr_candidate": needs_ocr,
                    "table_preservation": "requires_visual_review" if tables else "not_proven",
                    "has_warning": bool(re.search(r"ADVERTÊNCIA|CUIDADO|ATENÇÃO", text)),
                    "review_status": "review_required",
                    "recovery_key": key,
                }
            )
        summary = {
            "document_sha256": sha,
            "pages_processed": len(pages),
            "native_text_changed_pages": sum(p["metrics"]["text_changed"] for p in pages),
            "native_encoding_improved_pages": sum(
                p["metrics"]["before_invalid_ratio"] > p["metrics"]["after_invalid_ratio"]
                for p in pages
            ),
            "pages_needing_ocr_or_review": sum(p["ocr_candidate"] for p in pages),
            "pages_with_processing_failures": sum(bool(p["failures"]) for p in pages),
            "pages_quarantined": len(pages),
            "table_candidates": sum(len(p["tables"]) for p in pages),
            "table_candidates_approved": 0,
            "before_invalid_ratio": sum(
                p["metrics"]["before_invalid_ratio"] * p["metrics"]["before_characters"]
                for p in pages
            )
            / max(1, sum(p["metrics"]["before_characters"] for p in pages)),
            "after_invalid_ratio": sum(
                p["metrics"]["after_invalid_ratio"] * p["metrics"]["after_characters"]
                for p in pages
            )
            / max(1, sum(p["metrics"]["after_characters"] for p in pages)),
            "remaining_issue_counts": dict(
                Counter(issue for p in pages for issue in p["metrics"]["after_issues"])
            ),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "approval_status": "pending",
        }
        artifact = {
            "config": config,
            "recovery_key": key,
            "font_maps": changed,
            "summary": summary,
            "pages": pages,
        }
        artifact = refresh_quality(artifact, original)
        summary = artifact["summary"]
        atomic_json(destination, artifact)
        original.close()
        derived.close()
        results.append(summary)
        print(json.dumps({"document": sha[:12], **summary}), flush=True)
    results = [
        json.loads(p.read_text())["summary"] for p in sorted((output / "documents").glob("*.json"))
    ]
    result = {
        "strategy": RECOVERY_VERSION,
        "documents": results,
        "total_pages": sum(r["pages_processed"] for r in results),
        "approved_sections": 0,
        "ocr_executed_in_native_pass": False,
        "llm_calls": 0,
        "embedding_calls": 0,
    }
    atomic_json(output / "summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--document", help="Full document SHA-256; resume one document")
    args = parser.parse_args()
    if args.output.resolve() == args.catalog.resolve() or args.output.resolve().is_relative_to(
        args.catalog.resolve()
    ):
        parser.error("Keep recovery output separate from Checkpoint A artifacts")
    recover_all(args.catalog, args.output, args.document)
