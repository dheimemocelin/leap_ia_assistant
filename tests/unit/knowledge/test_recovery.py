from pathlib import Path

import pytest

from app.knowledge.recovery import (
    cmap_bytes,
    digest_text,
    extract_tables,
    family,
    invalid_ratio,
    page_metrics,
)


def test_font_identity_and_ligature_mapping_preserve_numbers():
    assert (
        family("ABCDEF+HarmonyOS_Sans_SC_Light-GBK-EUC-H-Identity-H") == "HarmonyOS_Sans_SC_Light"
    )
    result = cmap_bytes({453: "rt", 2: " ", 42: "3", 43: ",", 44: "6"})
    assert b"<01c5><00720074>" in result
    assert b"<002a><0033>" in result and b"<002b><002c>" in result


def test_quality_is_not_semantic_approval():
    metrics = page_metrics("Bateria\ufffd", "Bateria 56 kWh")
    assert metrics["after_invalid_ratio"] == 0
    assert metrics["semantic_correctness"] == "not_automatically_validated"
    assert invalid_ratio("3,6 kW\n220 V") == 0


def test_native_mapping_does_not_mutate_original_in_memory():
    fitz = pytest.importorskip("pymupdf")
    pytest.importorskip("fontTools")
    from app.knowledge.recovery import derived_document

    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.exists():
        pytest.skip("Controlled test font unavailable")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_font(fontname="testfont", fontfile=str(font))
    page.insert_text((30, 50), "Carregamento: 3,6 kW 220 V", fontname="testfont")
    doc = fitz.open(stream=doc.tobytes(), filetype="pdf")
    before = digest_text(doc.xref_object(1))
    original_xrefs = doc.xref_length()
    original_text = doc[0].get_text()
    recovered, maps = derived_document(doc, "a" * 64, {})
    assert maps
    assert doc.xref_length() == original_xrefs
    assert digest_text(doc.xref_object(1)) == before
    assert doc[0].get_text() == original_text
    assert "3,6 kW 220 V" in recovered[0].get_text()


def test_structured_table_keeps_headers_units_and_rows():
    fitz = pytest.importorskip("pymupdf")
    doc = fitz.open()
    p = doc.new_page()
    for y in [40, 70, 100]:
        p.draw_line((40, y), (260, y))
    for x in [40, 150, 260]:
        p.draw_line((x, 40), (x, 100))
    for x, y, text in [
        (45, 60, "Item"),
        (155, 60, "Valor"),
        (45, 90, "Potencia"),
        (155, 90, "3,6 kW"),
    ]:
        p.insert_text((x, y), text)
    tables = extract_tables(p)
    assert tables
    assert tables[0]["rows"] == [["Item", "Valor"], ["Potencia", "3,6 kW"]]
    assert tables[0]["review_status"] == "review_required"


def test_portuguese_uppercase_accents_are_not_mojibake():
    from app.knowledge.extraction import text_issues

    assert "encoding_suspect" not in text_issues("AÇÃO, CÂMERA, SEGURANÇA E DIREÇÃO")
    assert "encoding_suspect" in text_issues("InformaÃ§Ã£o corrompida")


def test_nfc_normalization_does_not_rewrite_values_or_units():
    import unicodedata

    value = "Pote\u0302ncia: 3,6 kW; tensão: 220 V; 10–80%; B10 BEV MY2027"
    normalized = unicodedata.normalize("NFC", value)
    for expected in ["3,6 kW", "220 V", "10–80%", "B10 BEV MY2027"]:
        assert expected in normalized


def test_tsv_preserves_decimal_units_and_line_boundaries():
    from app.knowledge.ocr import tsv_text

    raw = "level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
    raw += "5\t1\t1\t1\t1\t95\t3,6\n5\t1\t1\t1\t1\t91\tkW\n5\t1\t1\t1\t2\t80\t220V\n"
    text, confidence = tsv_text(raw)
    assert text == "3,6 kW\n220V" and confidence == [95, 91, 80]


def test_zero_invalid_characters_do_not_override_missing_font_map():
    from app.knowledge.recover_cli import refresh_quality

    class Page:
        def get_text(self, **kw):
            return "HQWUDGD sem caracteres inválidos mas codificação incorreta"

        def get_fonts(self, **kw):
            return [(123, "cid", "Type0", "Arial", "G1", "Identity-H")]

    class Original:
        def __getitem__(self, i):
            return Page()

        def xref_get_key(self, *args):
            return ("null", "null")

    text = "HQWUDGD sem caracteres inválidos mas codificação incorreta"
    artifact = {
        "font_maps": [],
        "summary": {},
        "pages": [{"page": 1, "text": text, "text_sha256": digest_text(text)}],
    }
    result = refresh_quality(artifact, Original())
    assert result["pages"][0]["metrics"]["after_invalid_ratio"] == 0
    assert result["pages"][0]["ocr_candidate"]
    assert "unmapped_identity_font" in result["pages"][0]["metrics"]["after_issues"]


def test_recovered_cache_tampering_is_not_remeasured_as_valid():
    from app.knowledge.recover_cli import refresh_quality

    with pytest.raises(ValueError, match="integrity"):
        refresh_quality({"pages": [{"text": "changed", "text_sha256": "a" * 64}]}, None)
