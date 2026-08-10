from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Mapping


_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "；": ";",
        "：": ":",
        "！": "!",
        "？": "?",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)


@dataclass(frozen=True)
class EvidenceMatch:
    matched: bool
    text_coverage: float
    page_match: bool


def normalize_text(value: str) -> str:
    """Normalize Unicode, punctuation, newlines, and all whitespace."""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.translate(_PUNCTUATION_TRANSLATION)
    return re.sub(r"\s+", "", normalized).casefold()


def _field(value: Any, *names: str) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return None
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return None


def _text_coverage(retrieved_text: str, gold_text: str) -> float:
    retrieved = normalize_text(retrieved_text)
    gold = normalize_text(gold_text)
    if not retrieved or not gold:
        return 0.0
    if gold in retrieved:
        return 1.0
    # Chunk boundaries usually remove a contiguous prefix or suffix. Longest
    # common substring measures that coverage without rewarding reordered text.
    common = SequenceMatcher(None, gold, retrieved, autojunk=False).find_longest_match()
    return common.size / len(gold)


def _same_page(retrieved_page: Any, expected_page: Any) -> bool:
    if retrieved_page is None or expected_page is None:
        return False
    try:
        return int(retrieved_page) == int(expected_page)
    except (TypeError, ValueError):
        return False


def _page_values(value: Any) -> list[int]:
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if not isinstance(decoded, (list, tuple, set)):
        return []
    pages: set[int] = set()
    for page in decoded:
        try:
            normalized = int(page)
        except (TypeError, ValueError):
            continue
        if normalized > 0:
            pages.add(normalized)
    return sorted(pages)


def _matches_candidate_page(retrieved_chunk: Any, expected_page: Any) -> bool:
    retrieved_pages = _page_values(_field(retrieved_chunk, "page_nos"))
    if not retrieved_pages:
        metadata = _field(retrieved_chunk, "metadata")
        if isinstance(metadata, Mapping):
            retrieved_pages = _page_values(metadata.get("page_nos"))
    if retrieved_pages:
        try:
            return int(expected_page) in retrieved_pages
        except (TypeError, ValueError):
            return False
    retrieved_page = _field(retrieved_chunk, "page", "page_no")
    return _same_page(retrieved_page, expected_page)


def match_evidence(
    retrieved_chunk: Any,
    expected_evidence: Any,
    min_text_coverage: float = 0.7,
    require_page_match: bool = True,
) -> EvidenceMatch:
    if not 0.0 <= min_text_coverage <= 1.0:
        raise ValueError("min_text_coverage must be between 0 and 1")

    expected_page = _field(expected_evidence, "page", "page_no", "gold_page_no")
    page_match = _matches_candidate_page(retrieved_chunk, expected_page)
    coverage = _text_coverage(
        str(_field(retrieved_chunk, "text", "snippet", "page_content") or ""),
        str(_field(expected_evidence, "text", "excerpt", "gold_excerpt") or ""),
    )
    matched = coverage >= min_text_coverage and (page_match or not require_page_match)
    return EvidenceMatch(matched=matched, text_coverage=coverage, page_match=page_match)
