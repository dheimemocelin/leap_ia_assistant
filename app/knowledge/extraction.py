"""Bounded offline subprocess entrypoint. Raw PDF text remains untrusted."""

import json
import re
import sys
import unicodedata
from collections import Counter

PIPELINE_VERSION = "audit-v1"


def text_issues(text):
    issues = []
    if len(text.strip()) < 40:
        issues.append("sparse_text_or_image_only")
    invalid = sum(
        c == "\ufffd" or unicodedata.category(c) in {"Co", "Cc"} and c not in "\n\r\t" for c in text
    )
    unusual = sum("\u0180" <= c <= "\u024f" or "\u4e00" <= c <= "\u9fff" for c in text)
    if unusual > 2:
        issues.append("unexpected_glyphs_or_language")
    if invalid or re.search(r"\(cid:\d+\)|Ã[\u0080-\u00bf]|Â[\u0080-\u00bf]|â€", text):
        issues.append("encoding_suspect")
    words = re.findall(r"[^\W\d_]+", text)
    if len(words) > 20 and sum(len(w) == 1 for w in words) / len(words) > 0.3:
        issues.append("fragmented_words")
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 20]
    if lines and max(Counter(lines).values()) >= 3:
        issues.append("repeated_text")
    if re.search(
        r"conforme.*(?:vers[aã]o|configura)|se equipado|opcional|depend.*vers[aã]o",
        text,
        re.IGNORECASE,
    ):
        issues.append("equipment_applicability_requires_review")
    if re.search(
        r"ignore.*instru|system prompt|api[_ -]?key|execute.*comando", text, re.IGNORECASE
    ):
        issues.append("untrusted_instruction_suspect")
    if re.search(
        r"a traduç[ãa]o atual|traduç[ãa]o atualizada|texto-fonte.*termo especificado",
        text,
        re.IGNORECASE,
    ):
        issues.append("editorial_translation_artifact")
    return issues


def extract(path):
    import pymupdf
    import pypdf

    reader = pypdf.PdfReader(path, strict=False)
    if reader.is_encrypted:
        raise ValueError("encrypted_document")
    if len(reader.pages) > 1000:
        raise ValueError("page_limit_exceeded")
    alternate = pymupdf.open(path)
    if len(alternate) != len(reader.pages):
        raise ValueError("extractor_page_count_mismatch")
    pages = []
    for index, page in enumerate(reader.pages):
        failures = []
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - quarantine malformed PDF pages; no raw parser error logs
            text = ""
            failures.append("primary_extraction_failed")
        try:
            other = alternate[index].get_text(sort=True)
        except Exception:  # noqa: BLE001 - quarantine malformed PDF pages; no raw parser error logs
            other = ""
            failures.append("alternate_extraction_failed")
        issues = list(dict.fromkeys(failures + text_issues(text) + text_issues(other)))
        if len(text.strip()) and len(other.strip()):
            ratio = min(len(text), len(other)) / max(len(text), len(other))
            if ratio < 0.65:
                issues.append("extractors_disagree")
        # No automatic correction or preferred extractor promotion.
        pages.append(
            {
                "page": index + 1,
                "text": text[:60000],
                "alternate_text": other[:60000],
                "issues": issues,
                "images": len(alternate[index].get_images()),
                "extraction_methods": ["pypdf", "pymupdf"],
            }
        )
        if len(text) > 60000 or len(other) > 60000:
            pages[-1]["issues"].append("page_text_truncated")
    metadata = reader.metadata or {}
    return {
        "pages": pages,
        "pdf_metadata": {
            key: str(metadata[key])[:2000] if metadata.get(key) is not None else None
            for key in ["/Title", "/Subject", "/CreationDate", "/ModDate", "/Producer"]
        },
        "extractor_versions": {"pypdf": pypdf.__version__, "pymupdf": pymupdf.VersionBind},
    }


if __name__ == "__main__":
    # PDF parsers are not a sandbox; OS resource ceilings and offline invocation
    # limit accidents. Run hostile PDFs in a disposable network-isolated container.
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (150, 150))
    try:
        print(json.dumps(extract(sys.argv[1]), ensure_ascii=False))
    except Exception:  # noqa: BLE001 - quarantine malformed PDF pages; no raw parser error logs
        print(json.dumps({"error": "pdf_extraction_failed"}))
        sys.exit(2)
