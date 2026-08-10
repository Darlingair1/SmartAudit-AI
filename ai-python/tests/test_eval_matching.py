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
