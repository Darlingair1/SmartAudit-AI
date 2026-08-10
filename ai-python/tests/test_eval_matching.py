from eval.matching.evidence_matcher import match_evidence


def test_exact_and_normalized_matches():
    gold = {"page": 2, "text": "责任\n以合同总价为上限"}
    assert match_evidence({"page_no": 2, "snippet": gold["text"]}, gold).matched
    assert match_evidence(
        {"page_no": 2, "snippet": " 责任 以合同总价为上限 "}, gold
    ).matched
    assert match_evidence(
        {"page_no": 2, "snippet": "责任：以合同总价为上限"},
        {"page": 2, "text": "责任:以合同总价为上限"},
    ).matched


def test_partial_coverage_threshold_and_page_rules():
    gold = {"page": 2, "text": "甲方应在收到发票后十个工作日内付款"}
    partial = {"page": 2, "snippet": "收到发票后十个工作日内付款"}
    assert match_evidence(partial, gold, min_text_coverage=0.7).matched
    assert not match_evidence(partial, gold, min_text_coverage=0.95).matched
    assert not match_evidence({"page": 3, "snippet": partial["snippet"]}, gold).matched
    assert not match_evidence({"snippet": partial["snippet"]}, gold).matched
    assert match_evidence(
        {"snippet": partial["snippet"]}, gold, require_page_match=False
    ).matched


def test_multi_page_candidate_matches_gold_on_any_covered_page():
    candidate = {
        "page_no": 3,
        "page_nos": [3, 4],
        "snippet": "跨页合同证据",
    }
    assert match_evidence(candidate, {"page": 4, "text": "跨页合同证据"}).matched
    assert not match_evidence(candidate, {"page": 5, "text": "跨页合同证据"}).matched


def test_empty_page_nos_falls_back_to_legacy_page_no():
    candidate = {"page_no": 4, "page_nos": [], "snippet": "合同证据"}
    assert match_evidence(candidate, {"page": 4, "text": "合同证据"}).matched
    assert not match_evidence(candidate, {"page": 3, "text": "合同证据"}).matched


def test_missing_gold_page_keeps_existing_page_match_behavior():
    candidate = {"page_no": 4, "page_nos": [3, 4], "snippet": "合同证据"}
    gold = {"text": "合同证据"}
    assert not match_evidence(candidate, gold).matched
    assert match_evidence(candidate, gold, require_page_match=False).matched
