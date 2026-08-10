from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


SupportStatus = Literal["SUPPORTED", "WEAK_SUPPORTED", "UNSUPPORTED"]
JudgeDecision = Literal["YES", "NO", "UNCERTAIN"]


@dataclass
class SecurityContext:
    tenant_id: str
    org_id: str
    user_id: str
    permission_scope: str
    task_id: str
    document_id: str
    contract_id: str

    def short(self) -> Dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "org_id": self.org_id,
            "user_id": self.user_id,
            "permission_scope": self.permission_scope,
            "task_id": self.task_id,
            "document_id": self.document_id,
            "contract_id": self.contract_id,
        }


@dataclass
class ParentChunk:
    parent_id: str
    text: str
    page_start: int
    page_end: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChildChunk:
    child_id: str
    parent_id: str
    text: str
    page_no: int
    offset_start: int
    offset_end: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    page_start: int | None = None
    page_end: int | None = None
    page_nos: List[int] = field(default_factory=list)


@dataclass
class RetrievalCandidate:
    candidate_id: str
    parent_id: str
    child_id: str
    page_no: int
    clause_id: str
    clause_title: str
    snippet: str
    bm25_rank: int | None = None
    vector_rank: int | None = None
    rrf_score: float = 0.0
    query_source: str = ""
    matched_terms: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    page_start: int | None = None
    page_end: int | None = None
    page_nos: List[int] = field(default_factory=list)


@dataclass
class JudgeResult:
    decision: JudgeDecision
    confidence: float
    reason_code: str
    reason: str
    supporting_evidence_ids: List[str]
    missing_evidence_hint: str = ""
    requires_human_review: bool = False


@dataclass
class ClaimCheck:
    claim_id: str
    claim_text: str
    support_status: SupportStatus
    supporting_evidence_ids: List[str]
    reason_code: str


@dataclass
class FinalCheckResult:
    claims: List[ClaimCheck]
    overall_support_status: SupportStatus
    unsupported_claims: List[str]
    requires_human_review: bool
