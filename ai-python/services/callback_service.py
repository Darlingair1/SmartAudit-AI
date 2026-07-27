import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import List, Tuple
from uuid import uuid4

import requests

from core.config import get_settings
from schemas.models import (
    AuditCallbackPayload,
    AuditJobRequest,
    CallbackError,
    CallbackSummary,
    RiskItem,
)


def build_success_payload(
    job_request: AuditJobRequest,
    python_job_id: str,
    summary: CallbackSummary,
    risk_items: List[RiskItem],
) -> AuditCallbackPayload:
    return AuditCallbackPayload(
        callbackId=f"cb_{uuid4().hex}",
        taskId=job_request.taskId,
        taskNo=job_request.taskNo,
        pythonJobId=python_job_id,
        status="COMPLETED",
        finishedAt=datetime.utcnow(),
        summary=summary,
        riskItems=risk_items,
        error=None,
    )


def build_failed_payload(
    job_request: AuditJobRequest,
    python_job_id: str,
    error_code: str,
    error_message: str,
) -> AuditCallbackPayload:
    return AuditCallbackPayload(
        callbackId=f"cb_{uuid4().hex}",
        taskId=job_request.taskId,
        taskNo=job_request.taskNo,
        pythonJobId=python_job_id,
        status="FAILED",
        finishedAt=datetime.utcnow(),
        summary=CallbackSummary(
            riskTotal=0,
            highRiskCount=0,
            mediumRiskCount=0,
            lowRiskCount=0,
        ),
        riskItems=[],
        error=CallbackError(code=error_code, message=error_message),
    )


def _canonical_payload_json(payload: AuditCallbackPayload) -> str:
    payload_dict = payload.model_dump(mode="json")
    return json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":"))


def _sign_payload(body: str, secret: str) -> Tuple[str, str, str]:
    timestamp = str(int(time.time()))
    nonce = uuid4().hex
    sign_source = f"{timestamp}\n{nonce}\n{body}"
    signature = hmac.new(secret.encode("utf-8"), sign_source.encode("utf-8"), hashlib.sha256).hexdigest()
    return timestamp, nonce, signature


def _do_post_callback(job_request: AuditJobRequest, payload: AuditCallbackPayload) -> requests.Response:
    settings = get_settings()
    payload_json = _canonical_payload_json(payload)
    headers = {"Content-Type": "application/json"}
    if job_request.callbackToken:
        headers["X-Callback-Token"] = job_request.callbackToken

    if settings.callback_signature_enabled:
        if not settings.callback_signature_secret:
            raise RuntimeError("callback signature enabled but CALLBACK_SIGNATURE_SECRET is empty")
        timestamp, nonce, signature = _sign_payload(payload_json, settings.callback_signature_secret)
        headers["X-Callback-Timestamp"] = timestamp
        headers["X-Callback-Nonce"] = nonce
        headers["X-Callback-Signature"] = signature

    return requests.post(
        job_request.callbackUrl,
        data=payload_json.encode("utf-8"),
        headers=headers,
        timeout=settings.callback_timeout_seconds,
        verify=settings.callback_verify_ssl,
    )


async def send_callback(job_request: AuditJobRequest, payload: AuditCallbackPayload) -> None:
    settings = get_settings()
    retries = max(1, settings.callback_retry_times)
    for attempt in range(1, retries + 1):
        try:
            response = await asyncio.to_thread(_do_post_callback, job_request, payload)
            if 200 <= response.status_code < 300:
                return
            raise RuntimeError(f"callback failed with status={response.status_code}")
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(settings.callback_retry_interval_seconds)
