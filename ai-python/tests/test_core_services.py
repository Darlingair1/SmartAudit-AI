from pathlib import Path

import pytest

from core.config import Settings
from schemas.models import AuditJobRequest
from services.budget_controller import RiskBudget, budget_metrics_aggregate, build_risk_budget
from services.final_consistency_check import run_claim_level_final_check
from services.legal_tokenizer import expand_query_with_synonyms, tokenize_legal_text
from services.parser_quality_gate import analyze_parser_quality
from services.risk_query_builder import build_risk_queries
from services.security_context import build_security_context, permission_scope_hash
from services.trace_compliance import mask_pii, persist_trace_event
from services.v3_pipeline import (
    _build_chunk_ranges,
    _build_chunk_text,
    _compact_json,
    _count_levels,
    _dedupe_draft_items,
    _normalize_level,
    _normalize_page_no,
)
from services.v3_types import RetrievalCandidate


def test_parser_quality_covers_empty_and_good_documents() -> None:
    empty = analyze_parser_quality([])
    assert empty["parse_quality"] == "BAD"
    assert empty["fallback_required"] is True

    good = analyze_parser_quality(["合同正文 " * 30, "付款条款 " * 30])
    assert good["parse_quality"] == "GOOD"
    assert good["ocr_required"] is False


def test_chunking_and_draft_deduplication() -> None:
    assert _build_chunk_ranges(0, 10, 1) == []
    assert _build_chunk_ranges(5, 2, 1) == [(1, 2), (2, 3), (3, 4), (4, 5)]
    assert _build_chunk_text(["p1", "p2"], 1, 2) == "[Page 1]\np1\n\n[Page 2]\np2"

    items = [
        {"riskType": "PAYMENT", "clauseTitle": "Late", "pageNo": 1, "contractExcerpt": "same"},
        {"riskType": "PAYMENT", "clauseTitle": "Late", "pageNo": 1, "contractExcerpt": "same"},
        {"riskType": "OTHER", "clauseTitle": "Other", "pageNo": 1, "contractExcerpt": "different"},
    ]
    assert len(_dedupe_draft_items(items)) == 2


def test_v3_normalizers_and_summary_helpers() -> None:
    assert _normalize_level("high") == "HIGH"
    assert _normalize_level("invalid") == "LOW"
    assert _normalize_page_no("3", 1) == 3
    assert _normalize_page_no("bad", 2) == 2
    assert _count_levels([]) == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    assert _compact_json({"value": "x"}, 5).endswith("...(truncated)")


def test_budget_records_drops_and_aggregates() -> None:
    budget = RiskBudget(1, 10, 5, 3, 1, 200, 500)
    budget.record_drop(10, 4)
    budget.mark_exhausted()
    metrics = budget_metrics_aggregate([budget])
    assert metrics == {
        "budget_drop_count": 1.0,
        "budget_exhausted_rate": 1.0,
        "token_saved_per_risk": 6.0,
    }
    assert budget_metrics_aggregate([])["budget_drop_count"] == 0.0
    assert build_risk_budget(Settings()).max_expanded_queries >= 1


def test_query_tokenizer_and_risk_query_builder() -> None:
    tokens = tokenize_legal_text("付款违约 10%")
    assert tokens
    assert expand_query_with_synonyms("保密义务")
    result = build_risk_queries({"riskType": "PAYMENT", "clauseTitle": "付款", "riskDesc": "付款条件"})
    assert result["risk_type"] == "PAYMENT"
    assert result["expanded_queries"]


def _job(**overrides: str | None) -> AuditJobRequest:
    data = {
        "taskId": "task-1",
        "taskNo": "NO-1",
        "filePath": "/tmp/a.pdf",
        "fileName": "a.pdf",
        "callbackUrl": "http://callback",
        **overrides,
    }
    return AuditJobRequest(**data)


def test_security_context_defaults_and_strict_validation() -> None:
    context = build_security_context(_job(), Settings())
    assert context.task_id == "task-1"
    assert permission_scope_hash("audit:read") != permission_scope_hash("audit:write")

    strict = Settings(strict_tenant_isolation=True, tenant_filter_required=True)
    with pytest.raises(ValueError, match="tenantId"):
        build_security_context(_job(), strict)


def test_final_consistency_checks_supported_and_unsupported_claims() -> None:
    candidate = RetrievalCandidate("c1", "p1", "ch1", 1, "clause", "title", "payment deadline and penalty")
    supported = run_claim_level_final_check(
        risk_item={"riskDesc": "payment deadline", "suggestion": "review payment", "contractExcerpt": "payment"},
        evidence_candidates=[candidate],
    )
    assert supported.claims
    unsupported = run_claim_level_final_check(
        risk_item={"riskDesc": "unrelated claim", "suggestion": "unrelated suggestion", "contractExcerpt": ""},
        evidence_candidates=[],
    )
    assert unsupported.requires_human_review is True


def test_trace_compliance_masks_and_persists_without_full_text(tmp_path: Path) -> None:
    assert "***PHONE***" in mask_pii("contact 13800138000")
    context = build_security_context(_job(tenantId="tenant-a"), Settings())
    output = persist_trace_event(
        trace_dir=str(tmp_path),
        security_context=context,
        payload={"full_contract_text": "secret", "email": "a@example.com", "debug": {"x": 1}},
        debug_enabled=False,
        store_full_text=False,
        pii_masking_enabled=True,
        encryption_enabled=False,
        encryption_secret="",
        retention_days=0,
    )
    content = Path(output).read_text(encoding="utf-8")
    assert "secret" not in content
    assert "***EMAIL***" in content
