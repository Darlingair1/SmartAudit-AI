from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from core.config import Settings


@dataclass
class RiskBudget:
    max_expanded_queries: int
    max_candidates_before_rrf: int
    max_rrf_candidates: int
    max_rerank_candidates: int
    max_judge_evidence: int
    max_parent_context_tokens: int
    max_total_context_tokens: int
    budget_drop_count: int = 0
    budget_exhausted: bool = False
    token_saved_per_risk: int = 0

    def record_drop(self, expected: int, actual: int) -> None:
        if expected > actual:
            self.budget_drop_count += 1
            self.token_saved_per_risk += max(0, expected - actual)

    def mark_exhausted(self) -> None:
        self.budget_exhausted = True


def build_risk_budget(settings: Settings) -> RiskBudget:
    return RiskBudget(
        max_expanded_queries=max(1, settings.max_expanded_queries_per_risk),
        max_candidates_before_rrf=max(10, settings.max_risk_candidates_before_rrf),
        max_rrf_candidates=max(5, settings.max_rrf_candidates_per_risk),
        max_rerank_candidates=max(3, settings.max_rerank_candidates_per_risk),
        max_judge_evidence=max(1, settings.max_judge_evidence_per_risk),
        max_parent_context_tokens=max(200, settings.max_parent_context_tokens),
        max_total_context_tokens=max(500, settings.max_total_context_tokens_per_risk),
    )


def budget_metrics_aggregate(risk_budgets: list[RiskBudget]) -> Dict[str, float]:
    if not risk_budgets:
        return {"budget_drop_count": 0.0, "budget_exhausted_rate": 0.0, "token_saved_per_risk": 0.0}

    drop_count = sum(x.budget_drop_count for x in risk_budgets)
    exhausted = sum(1 for x in risk_budgets if x.budget_exhausted)
    token_saved = sum(x.token_saved_per_risk for x in risk_budgets)
    total = len(risk_budgets)
    return {
        "budget_drop_count": float(drop_count),
        "budget_exhausted_rate": round(exhausted / total, 4),
        "token_saved_per_risk": round(token_saved / total, 2),
    }

