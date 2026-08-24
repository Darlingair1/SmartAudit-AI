from services.evidence_judge_v2_1 import judge_claim_evidence_v2_1

def test_contradiction_overrides_semantic_coverage():
    x=judge_claim_evidence_v2_1("甲方支付百分之三十价款","甲方支付百分之二十价款")
    assert x["predicted_label"]=="UNSUPPORTED" and x["reason_code"]=="CONFLICT_DETECTED"

def test_related_but_insufficient_is_not_supported():
    x=judge_claim_evidence_v2_1("供应商必须在三十日内退款","供应商负责退款流程")
    assert x["predicted_label"]!="SUPPORTED"

def test_missing_material_segment_is_partial():
    x=judge_claim_evidence_v2_1("价款是多少，并且是否承诺最低支出？","合同价款为十万元")
    assert x["predicted_label"]=="PARTIAL"

def test_true_multi_evidence_support_remains_supported():
    claim="甲方支付全部价款，付款期限为收到发票后十个工作日"; evidence="甲方支付全部价款。付款期限为收到发票后十个工作日。"
    assert judge_claim_evidence_v2_1(claim,evidence)["predicted_label"]=="SUPPORTED"

def test_unrelated_evidence_is_unsupported_with_reason():
    x=judge_claim_evidence_v2_1("合同如何约定保密责任？","车辆应当按时交付")
    assert x["predicted_label"]=="UNSUPPORTED"
    assert x["reason_code"]=="SEMANTIC_RELEVANCE_NOT_SUFFICIENCY"

def test_frozen_inputs_and_previous_judges_unchanged():
    import hashlib
    from pathlib import Path
    root=Path(__file__).parents[1]
    expected={
        "eval/judge/claim_evidence_generalization_v1.jsonl":"8b171081aa27a07e7e4d9d0b4ccc8de75e28926aa582822a04985182b7831d8e",
        "services/evidence_judge.py":"557befaba4ca5b044f4b01262eabc66f5e1f03cd77caa77c95a0eeddbb9ee2d3",
        "services/evidence_judge_v1.py":"041633435db6feb2da1814a1638c0308c0b3e484d27fea93b11994ccccb21bc5",
        "services/evidence_judge_v2.py":"32b0d8bf40ee4f8e93b1df1d72c01dd04337500821e6c88ba7a384bcdc959f20",
    }
    for relative,digest in expected.items(): assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==digest

def test_acceptance_result_is_machine_computed_and_frozen():
    import json
    from pathlib import Path
    root=Path(__file__).parents[1]/"eval/experiments/evidence_judge_v2_safety_hardening_20260823"
    result=json.loads((root/"acceptance_result.json").read_text(encoding="utf8"))
    assert result["overall_pass"] is False
    assert result["insufficient_evidence_gate"] is False
    assert sum(not value for key,value in result.items() if key!="overall_pass")==1
