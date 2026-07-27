from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


EvidenceRole = Literal["PRIMARY", "SUPPORTING", "EXCEPTION", "LIMITATION", "CONTRADICTORY"]


class GoldEvidence(BaseModel):
    gold_clause_id: Optional[str] = None
    gold_page_no: int = Field(..., ge=1)
    gold_excerpt: str
    evidence_role: EvidenceRole


class EvalSample(BaseModel):
    contract_id: str
    task_id: str
    risk_type: str
    risk_query: str
    gold_evidences: List[GoldEvidence]
    expected_decision: str
    expected_reason_code: str

