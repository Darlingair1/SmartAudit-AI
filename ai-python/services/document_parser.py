"""Canonical document extraction used by production and evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader


def load_pdf_pages(file_path: str | Path) -> list[str]:
    """Extract one stripped text value for every physical PDF page."""

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")
    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError("PDF content is empty")
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    if not any(pages):
        raise ValueError("PDF has no extractable text")
    return pages


def extraction_sha256(page_texts: Sequence[str]) -> str:
    """Hash canonical text while preserving physical page boundaries."""

    digest = hashlib.sha256()
    for index, text in enumerate(page_texts):
        if index:
            digest.update(b"\n---PHYSICAL_PAGE_BOUNDARY---\n")
        digest.update(str(text).encode("utf-8"))
    return digest.hexdigest()
