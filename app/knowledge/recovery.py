"""Recover encoding using embedded glyph names, not inferred vehicle facts.

Only derived in-memory PDF copies are changed. All output stays unapproved.
Cross-document same-family maps are candidates requiring visual review.
"""

import hashlib
import re
import unicodedata
from io import BytesIO

from app.knowledge.extraction import text_issues

RECOVERY_VERSION = "glyph-recovery-v1"


def digest_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def family(name):
    name = name.split("+")[-1]
    return re.sub(r"-(?:GBK|Identity).*", "", name).rstrip("-")


def glyph_maps(document, document_hash):
    from fontTools.agl import toUnicode
    from fontTools.ttLib import TTFont

    maps = {}
    seen = set()
    for page in document:
        for entry in page.get_fonts(full=True):
            xref, ext, _, name = entry[:4]
            if xref in seen or ext != "ttf":
                continue
            seen.add(xref)
            _, _, _, buffer = document.extract_font(xref)
            if not buffer:
                continue
            with TTFont(BytesIO(buffer)) as font:
                mapping = {
                    i: toUnicode(n)
                    for i, n in enumerate(font.getGlyphOrder())
                    if toUnicode(n) and i <= 65535
                }
            # Only Identity-H CID codes equal glyph IDs. Never apply to WinAnsi fonts.
            if entry[5] != "Identity-H" or not mapping:
                continue
            key = family(name)
            evidence = {
                "reference_document_sha256": document_hash,
                "reference_font_sha256": hashlib.sha256(buffer).hexdigest(),
                "reference_font_name": name,
                "mapping": mapping,
            }
            if key in maps and maps[key]["mapping"] != mapping:
                raise ValueError("Conflicting embedded glyph-name mappings")
            maps[key] = evidence
    return maps


def cmap_bytes(mapping):
    entries = [
        f"<{i:04x}><{text.encode('utf-16-be').hex()}>" for i, text in sorted(mapping.items())
    ]
    chunks = []
    for offset in range(0, len(entries), 100):
        batch = entries[offset : offset + 100]
        chunks.append(f"{len(batch)} beginbfchar\n" + "\n".join(batch) + "\nendbfchar")
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /LiaRecovery def\n/CMapType 2 def\n1 begincodespacerange\n"
        "<0000><ffff>\nendcodespacerange\n"
        + "\n".join(chunks)
        + "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode()


def derived_document(document, document_hash, references):
    """Return a fresh memory copy, never save over the supplied original."""
    import pymupdf

    document = pymupdf.open(stream=document.tobytes(), filetype="pdf")
    own = glyph_maps(document, document_hash)
    maps = {**references, **own}
    changed, seen = [], set()
    for page in document:
        for entry in page.get_fonts(full=True):
            xref, _, kind, name = entry[:4]
            key = family(name)
            if xref in seen or kind != "Type0" or entry[5] != "Identity-H" or key not in maps:
                continue
            seen.add(xref)
            # A CIDToGIDMap stream may reorder glyph IDs. Require Identity or absence (CFF).
            descendants = document.xref_get_key(xref, "DescendantFonts")[1]
            match = re.search(r"(\d+) 0 R", descendants)
            if not match:
                continue
            cidmap = document.xref_get_key(int(match[1]), "CIDToGIDMap")
            if (
                cidmap[0] not in {"null", "name"}
                or cidmap[0] == "name"
                and cidmap[1] != "/Identity"
            ):
                continue
            source = maps[key]
            stream = document.get_new_xref()
            document.update_object(stream, "<<>>")
            document.update_stream(stream, cmap_bytes(source["mapping"]))
            document.xref_set_key(xref, "ToUnicode", f"{stream} 0 R")
            changed.append(
                {
                    "font_xref": xref,
                    "font_name": name,
                    **{k: v for k, v in source.items() if k != "mapping"},
                    "basis": "embedded_glyph_names" if key in own else "reference_family_candidate",
                }
            )
    recovered = pymupdf.open(stream=document.tobytes(), filetype="pdf")
    document.close()
    return recovered, changed


def invalid_ratio(text):
    invalid = sum(
        c == "\ufffd" or unicodedata.category(c) in {"Co", "Cc"} and c not in "\n\r\t" for c in text
    )
    return invalid / len(text) if text else 0.0


def page_metrics(before, after):
    return {
        "before_invalid_ratio": invalid_ratio(before),
        "after_invalid_ratio": invalid_ratio(after),
        "before_characters": len(before),
        "after_characters": len(after),
        "text_changed": before != after,
        "after_issues": text_issues(after),
        "semantic_correctness": "not_automatically_validated",
    }


def extract_blocks(page):
    """Keep source block/line/span coordinates instead of flattening table layout."""
    blocks = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block["type"] != 0:
            continue
        lines = []
        for line in block["lines"]:
            text = unicodedata.normalize("NFC", "".join(s["text"] for s in line["spans"]))
            lines.append(
                {
                    "bbox": list(line["bbox"]),
                    "text": text,
                    "spans": [
                        {
                            "text": s["text"],
                            "bbox": list(s["bbox"]),
                            "font": s["font"],
                            "size": s["size"],
                        }
                        for s in line["spans"]
                    ],
                }
            )
        blocks.append(
            {
                "bbox": list(block["bbox"]),
                "lines": lines,
                "text": "\n".join(line["text"] for line in lines),
            }
        )
    return blocks


def extract_tables(page):
    """Geometric candidate tables. Header/cells/bbox stay together and unapproved."""
    tables = []
    for table in page.find_tables().tables:
        tables.append(
            {
                "bbox": list(table.bbox),
                "rows": table.extract(),
                "header": table.header.names,
                "header_external": table.header.external,
                "review_status": "review_required",
            }
        )
    return tables
