from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from services.v3_types import SecurityContext


def mask_pii(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"1[3-9]\d{9}", "***PHONE***", value)
    value = re.sub(r"\b\d{15,18}[0-9Xx]?\b", "***ID***", value)
    value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "***EMAIL***", value)
    return value


def _xor_encrypt(content: str, secret: str) -> str:
    if not secret:
        return content
    data = content.encode("utf-8")
    key = hashlib.sha256(secret.encode("utf-8")).digest()
    out = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
    return base64.b64encode(out).decode("utf-8")


def _purge_old_files(trace_dir: Path, retention_days: int) -> None:
    if retention_days <= 0:
        return
    threshold = datetime.utcnow() - timedelta(days=retention_days)
    for file in trace_dir.glob("*.json*"):
        try:
            mtime = datetime.utcfromtimestamp(file.stat().st_mtime)
            if mtime < threshold:
                file.unlink(missing_ok=True)
        except Exception:
            continue


def persist_trace_event(
    *,
    trace_dir: str,
    security_context: SecurityContext,
    payload: Dict[str, Any],
    debug_enabled: bool,
    store_full_text: bool,
    pii_masking_enabled: bool,
    encryption_enabled: bool,
    encryption_secret: str,
    retention_days: int,
) -> str:
    trace_root = Path(trace_dir)
    trace_root.mkdir(parents=True, exist_ok=True)
    tenant_dir = trace_root / security_context.tenant_id / security_context.task_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    _purge_old_files(trace_root, retention_days)

    cleaned = dict(payload)
    if not debug_enabled:
        cleaned.pop("debug", None)
    if not store_full_text:
        cleaned.pop("full_contract_text", None)
        if "review_context" in cleaned:
            cleaned["review_context"] = str(cleaned["review_context"])[:1200]
    if pii_masking_enabled:
        cleaned = json.loads(mask_pii(json.dumps(cleaned, ensure_ascii=False)))

    content = json.dumps(cleaned, ensure_ascii=False, indent=2)
    suffix = "json"
    if encryption_enabled:
        content = _xor_encrypt(content, encryption_secret)
        suffix = "enc"

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    fp = tenant_dir / f"trace_{ts}.{suffix}"
    fp.write_text(content, encoding="utf-8")
    return str(fp)

