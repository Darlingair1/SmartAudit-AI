import logging
from datetime import datetime
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException

from core.config import get_settings
from schemas.models import (
    AuditJobAcceptedResponse,
    AuditJobRequest,
    VectorCleanupRequest,
    VectorCleanupResponse,
)
from services.audit_agent import cleanup_task_vector_index, run_contract_audit
from services.callback_service import (
    build_failed_payload,
    build_success_payload,
    send_callback,
)

settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("smartaudit.ai")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="SmartAudit-AI FastAPI + LangChain microservice",
)


def validate_security_settings() -> None:
    if settings.llm_provider not in {"deepseek", "openai-compatible"}:
        raise RuntimeError("LLM_PROVIDER must be deepseek or openai-compatible")
    production = settings.app_env.strip().lower() in {"prod", "production"}
    if not production:
        return
    if len(settings.internal_api_token) < 32:
        raise RuntimeError("INTERNAL_API_TOKEN must contain at least 32 characters in production")
    if not settings.callback_signature_enabled or len(settings.callback_signature_secret) < 32:
        raise RuntimeError("callback signing with a secret of at least 32 characters is required in production")


@app.on_event("startup")
async def _startup_log() -> None:
    validate_security_settings()
    logger.info(
        "AI service started, model=%s, base_url=%s",
        settings.default_model,
        settings.openai_base_url or "default",
    )


def _gen_python_job_id() -> str:
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"pyjob_{now}_{uuid4().hex[:8]}"


async def process_audit_job(job_request: AuditJobRequest, python_job_id: str) -> None:
    try:
        summary, risk_items = await run_contract_audit(job_request)
        payload = build_success_payload(job_request, python_job_id, summary, risk_items)
    except Exception as ex:
        logger.exception("Audit failed, taskId=%s, pythonJobId=%s", job_request.taskId, python_job_id)
        payload = build_failed_payload(
            job_request=job_request,
            python_job_id=python_job_id,
            error_code="AUDIT_PROCESS_ERROR",
            error_message=str(ex),
        )

    try:
        await send_callback(job_request, payload)
        logger.info(
            "Callback success, taskId=%s, pythonJobId=%s, status=%s",
            job_request.taskId,
            python_job_id,
            payload.status,
        )
    except Exception:
        logger.exception(
            "Callback failed after retries, taskId=%s, pythonJobId=%s",
            job_request.taskId,
            python_job_id,
        )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/internal/v1/ai/audit/jobs", response_model=AuditJobAcceptedResponse)
async def submit_audit_job(
    job_request: AuditJobRequest,
    background_tasks: BackgroundTasks,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> AuditJobAcceptedResponse:
    expected_token = (settings.internal_api_token or "").strip()
    if expected_token and expected_token != (x_internal_token or "").strip():
        raise HTTPException(status_code=401, detail="unauthorized")

    python_job_id = _gen_python_job_id()
    background_tasks.add_task(process_audit_job, job_request, python_job_id)
    return AuditJobAcceptedResponse(
        accepted=True,
        status="ACCEPTED",
        pythonJobId=python_job_id,
        message="task queued",
    )


@app.post(
    "/internal/v1/ai/audit/vector-index/cleanup",
    response_model=VectorCleanupResponse,
)
async def cleanup_vector_index(
    req: VectorCleanupRequest,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> VectorCleanupResponse:
    expected_token = (settings.internal_api_token or "").strip()
    if expected_token and expected_token != (x_internal_token or "").strip():
        raise HTTPException(status_code=401, detail="unauthorized")

    cleaned = cleanup_task_vector_index(req.taskId, settings)
    return VectorCleanupResponse(
        cleaned=cleaned,
        taskId=req.taskId,
        message="cleaned" if cleaned else "cleanup failed",
    )
