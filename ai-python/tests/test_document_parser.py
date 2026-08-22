from pathlib import Path

from eval.validate_benchmark import _load_document_pages
from services import audit_agent
from services import document_parser


PDF_PATH = Path(
    "eval/documents/public/jiyuan_vehicle_procurement_contract_2024_245_a.pdf"
)


def test_production_wrapper_and_canonical_loader_match() -> None:
    canonical = document_parser.load_pdf_pages(PDF_PATH)
    assert audit_agent._load_pdf_pages(str(PDF_PATH)) == canonical
    assert len(canonical) == 6


def test_validator_uses_canonical_loader(monkeypatch, tmp_path) -> None:
    pdf = tmp_path / "fixture.pdf"
    pdf.write_bytes(b"placeholder")
    expected = [" page one ", "", "page three"]
    monkeypatch.setattr(document_parser, "load_pdf_pages", lambda _: expected)
    assert _load_document_pages(pdf) == expected


def test_canonical_loader_strips_and_keeps_empty_page_slots(monkeypatch, tmp_path) -> None:
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class Reader:
        pages = [Page("  first  "), Page(None), Page("\n third\n")]

    pdf = tmp_path / "fixture.pdf"
    pdf.write_bytes(b"placeholder")
    monkeypatch.setattr(document_parser, "PdfReader", lambda _: Reader())
    assert document_parser.load_pdf_pages(pdf) == ["first", "", "third"]


def test_extraction_fingerprint_is_boundary_sensitive() -> None:
    assert document_parser.extraction_sha256(["a", "b"]) == document_parser.extraction_sha256(
        ["a", "b"]
    )
    assert document_parser.extraction_sha256(["a", "b"]) != document_parser.extraction_sha256(
        ["ab"]
    )
    assert document_parser.extraction_sha256(["a", "b"]) != document_parser.extraction_sha256(
        ["a", "c"]
    )
