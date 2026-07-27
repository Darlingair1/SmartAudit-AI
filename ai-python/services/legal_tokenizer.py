from __future__ import annotations

import re
from typing import List, Set

NEGATION_TERMS = {
    "不",
    "不承担",
    "不得",
    "不能",
    "无权",
    "除外",
    "除非",
    "但",
    "但书",
    "不超过",
}
PARTY_TERMS = {
    "甲方",
    "乙方",
    "委托方",
    "受托方",
    "买方",
    "卖方",
    "出租方",
    "承租方",
}
LEGAL_TERMS = {
    "违约金",
    "违约责任",
    "解除",
    "终止",
    "管辖",
    "仲裁",
    "争议解决",
    "保密",
    "商业秘密",
    "赔偿",
    "补偿",
    "知识产权",
}

SYNONYM_MAP = {
    "解除": ["终止", "提前终止", "解除权"],
    "赔偿": ["补偿", "损害赔偿"],
    "违约金": ["罚金", "违约责任"],
    "管辖": ["争议解决", "仲裁", "管辖法院"],
    "保密": ["商业秘密", "信息披露"],
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _extract_patterns(text: str) -> List[str]:
    patterns: List[str] = []
    patterns.extend(re.findall(r"\d+(?:\.\d+)?%|\d+‰", text))
    patterns.extend(re.findall(r"\d{4}年\d{1,2}月\d{1,2}日", text))
    patterns.extend(re.findall(r"\d+\s*(?:日|天|月|年|个工作日)", text))
    patterns.extend(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?\s*(?:元|万元|亿元|人民币)", text))
    patterns.extend(re.findall(r"[0-9]+(?:\.[0-9]+)*", text))
    return list(dict.fromkeys(patterns))


def _char_ngrams(text: str, min_n: int = 2, max_n: int = 4) -> List[str]:
    compact = re.sub(r"\s+", "", text)
    grams: List[str] = []
    for n in range(min_n, max_n + 1):
        for i in range(0, max(0, len(compact) - n + 1)):
            grams.append(compact[i : i + n])
    return grams


def tokenize_legal_text(text: str) -> List[str]:
    text = _normalize_text(text)
    if not text:
        return []

    tokens: Set[str] = set()
    for term in NEGATION_TERMS | PARTY_TERMS | LEGAL_TERMS:
        if term in text:
            tokens.add(term)

    for p in _extract_patterns(text):
        tokens.add(p)

    spans = re.findall(r"[\u4e00-\u9fffA-Za-z0-9\.%‰]+", text)
    for span in spans:
        if len(span) >= 2:
            tokens.add(span)

    for gram in _char_ngrams(text):
        if len(gram) >= 2:
            tokens.add(gram)

    return sorted(tokens)


def expand_query_with_synonyms(query: str) -> List[str]:
    query = _normalize_text(query)
    if not query:
        return []
    results = [query]
    for key, values in SYNONYM_MAP.items():
        if key in query:
            results.extend(values)
        for val in values:
            if val in query:
                results.append(key)
                results.extend(values)
    seen = set()
    out: List[str] = []
    for x in results:
        x = x.strip()
        if len(x) < 2 or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out

