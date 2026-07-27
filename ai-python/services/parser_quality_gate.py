from __future__ import annotations

import re
from typing import Any, Dict, Sequence


def analyze_parser_quality(page_texts: Sequence[str]) -> Dict[str, Any]:
    pages = [str(x or "") for x in page_texts]
    page_count = len(pages)
    non_empty = [x for x in pages if x.strip()]

    if page_count == 0:
        return {
            "parse_quality": "BAD",
            "ocr_required": True,
            "table_detected": False,
            "toc_detected": False,
            "header_footer_removed": False,
            "page_mapping_confidence": 0.0,
            "warnings": ["EMPTY_DOCUMENT"],
            "fallback_required": True,
        }

    table_pattern = re.compile(r"(\||│|┆|┊|┇|┋|┌|└|┬|┴|├|┤)")
    toc_pattern = re.compile(r"(目录|目\s*录|\.{3,}\s*\d+)")
    header_footer_pattern = re.compile(r"(第\s*\d+\s*页|page\s*\d+)", re.IGNORECASE)

    table_hits = 0
    toc_hits = 0
    header_hits = 0
    short_page_hits = 0
    for txt in pages:
        s = txt.strip()
        if len(s) < 60:
            short_page_hits += 1
        if table_pattern.search(s):
            table_hits += 1
        if toc_pattern.search(s):
            toc_hits += 1
        if header_footer_pattern.search(s):
            header_hits += 1

    ocr_required = (len(non_empty) / max(1, page_count) < 0.7) or (short_page_hits / max(1, page_count) > 0.4)
    table_detected = table_hits > 0
    toc_detected = toc_hits > 0
    header_footer_removed = header_hits < max(1, page_count // 3)

    warnings: list[str] = []
    if ocr_required:
        warnings.append("OCR_REQUIRED")
    if table_detected:
        warnings.append("TABLE_CLAUSE_DETECTED")
    if toc_detected:
        warnings.append("TOC_DETECTED")
    if not header_footer_removed:
        warnings.append("HEADER_FOOTER_POLLUTION")

    confidence = 0.95
    if ocr_required:
        confidence -= 0.25
    if toc_detected:
        confidence -= 0.08
    if table_detected:
        confidence -= 0.05
    if not header_footer_removed:
        confidence -= 0.12
    confidence = max(0.0, min(1.0, confidence))

    if confidence >= 0.85:
        quality = "GOOD"
    elif confidence >= 0.6:
        quality = "WARNING"
    else:
        quality = "BAD"

    return {
        "parse_quality": quality,
        "ocr_required": ocr_required,
        "table_detected": table_detected,
        "toc_detected": toc_detected,
        "header_footer_removed": header_footer_removed,
        "page_mapping_confidence": round(confidence, 4),
        "warnings": warnings,
        "fallback_required": quality == "BAD",
    }

