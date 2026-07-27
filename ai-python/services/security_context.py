from __future__ import annotations

import hashlib

from core.config import Settings
from schemas.models import AuditJobRequest
from services.v3_types import SecurityContext


def build_security_context(job_request: AuditJobRequest, settings: Settings) -> SecurityContext:
    tenant_id = (job_request.tenantId or "").strip()
    org_id = (job_request.orgId or "").strip()
    user_id = (job_request.userId or "").strip()
    scope = (job_request.permissionScope or "").strip()

    if not tenant_id:
        tenant_id = settings.default_tenant_id
    if not org_id:
        org_id = settings.default_org_id
    if not user_id:
        user_id = settings.default_user_id
    if not scope:
        scope = settings.default_permission_scope

    if settings.strict_tenant_isolation and settings.tenant_filter_required:
        missing = []
        if not (job_request.tenantId or "").strip():
            missing.append("tenantId")
        if not (job_request.orgId or "").strip():
            missing.append("orgId")
        if not (job_request.userId or "").strip():
            missing.append("userId")
        if not (job_request.permissionScope or "").strip():
            missing.append("permissionScope")
        if missing:
            raise ValueError(f"strict tenant isolation requires fields: {', '.join(missing)}")

    document_id = (job_request.documentId or "").strip() or f"doc-{job_request.taskId}"
    contract_id = (job_request.contractId or "").strip() or f"contract-{job_request.taskNo}"

    return SecurityContext(
        tenant_id=tenant_id,
        org_id=org_id,
        user_id=user_id,
        permission_scope=scope,
        task_id=str(job_request.taskId),
        document_id=document_id,
        contract_id=contract_id,
    )


def permission_scope_hash(scope: str) -> str:
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]

