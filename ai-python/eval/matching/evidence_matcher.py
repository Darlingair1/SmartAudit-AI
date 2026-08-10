from __future__ import annotations

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


def match_evidence(
    retrieved_chunk: Any,
    expected_evidence: Any,
    min_text_coverage: float = 0.7,
    require_page_match: bool = True,
) -> EvidenceMatch:
    if not 0.0 <= min_text_coverage <= 1.0:
        raise ValueError("min_text_coverage must be between 0 and 1")

    retrieved_page = _field(retrieved_chunk, "page", "page_no")
    expected_page = _field(expected_evidence, "page", "page_no", "gold_page_no")
    page_match = _same_page(retrieved_page, expected_page)
    coverage = _text_coverage(
        str(_field(retrieved_chunk, "text", "snippet", "page_content") or ""),
        str(_field(expected_evidence, "text", "excerpt", "gold_excerpt") or ""),
    )
    matched = coverage >= min_text_coverage and (page_match or not require_page_match)
    return EvidenceMatch(matched=matched, text_coverage=coverage, page_match=page_match)
