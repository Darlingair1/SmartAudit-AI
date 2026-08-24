from services.evidence_judge_v1 import judge_claim_evidence_v1

def test_v1_supported_when_claim_equals_evidence() -> None:
    result=judge_claim_evidence_v1('甲方应在10日内付款。','甲方应在10日内付款。')
    assert result['predicted_label']=='SUPPORTED'
    assert result['checks']['entity_consistency']['status']=='PASS'

def test_v1_detects_entity_conflict() -> None:
    result=judge_claim_evidence_v1('乙方应在10日内付款。','甲方应在10日内付款。')
    assert result['predicted_label']=='UNSUPPORTED'
    assert result['checks']['entity_consistency']['status']=='FAIL'

def test_v1_detects_numeric_and_temporal_conflict() -> None:
    result=judge_claim_evidence_v1('甲方应在11日内付款。','甲方应在10日内付款。')
    assert result['predicted_label']=='UNSUPPORTED'
    assert result['checks']['numeric_consistency']['status']=='FAIL'
    assert result['checks']['temporal_consistency']['status']=='FAIL'

def test_v1_abstains_for_missing_qualifier() -> None:
    result=judge_claim_evidence_v1('甲方应付款。在其他情况下是否也适用，证据没有说明。','甲方应付款。')
    assert result['predicted_label']=='PARTIAL'
    assert result['checks']['qualifier_completeness']['reason_code']=='QUALIFIER_MISSING'

def test_v1_detects_unsupported_risk_inference() -> None:
    result=judge_claim_evidence_v1('合同是否明确规定甲方承担刑事责任？','甲方应在10日内付款。')
    assert result['predicted_label']=='UNSUPPORTED'
    assert result['checks']['semantic_scope']['reason_code']=='UNSUPPORTED_RISK_INFERENCE'
