import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.knowledge.ocr import ocr_page


def test_selective_ocr_cache_and_missing_page(tmp_path, monkeypatch):
    fitz = pytest.importorskip("pymupdf")
    document = fitz.open()
    document.new_page()
    document.new_page()
    file = tmp_path / "source.pdf"
    file.write_bytes(document.tobytes())
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    binary = tmp_path / "tesseract"
    binary.write_bytes(b"synthetic engine")
    trained = tmp_path / "por.traineddata"
    trained.write_bytes(b"synthetic traineddata")
    calls = []
    raw = "level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n5\t1\t1\t1\t1\t95\t3,6kW\n"

    def run(args, **kw):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=raw.encode())

    monkeypatch.setattr("app.knowledge.ocr.subprocess.run", run)
    result = ocr_page(file, sha, 2, tmp_path / "out", binary=binary, tessdata=tmp_path)
    again = ocr_page(file, sha, 2, tmp_path / "out", binary=binary, tessdata=tmp_path)
    assert result == again and len(calls) == 1
    assert result["config"]["page"] == 2 and result["text"] == "3,6kW"
    assert result["review_status"] == "review_required"
    assert not list((tmp_path / "out").glob("**/*.png"))
    with pytest.raises(ValueError, match="outside"):
        ocr_page(file, sha, 3, tmp_path / "out", binary=binary, tessdata=tmp_path)


def test_ocr_does_not_accept_changed_original(tmp_path):
    p = tmp_path / "source.pdf"
    p.write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        ocr_page(p, "a" * 64, 1, tmp_path / "out", binary=Path("unused"), tessdata=tmp_path)
