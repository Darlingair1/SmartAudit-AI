from typing import Any

from fastapi import FastAPI

app = FastAPI()
calls: list[dict[str, str]] = []

_DRAFT_RESPONSE = {
    "draftRiskItems": [
        {
            "riskLevel": "HIGH",
            "riskType": "付款责任",
            "clauseTitle": "逾期付款责任",
            "pageNo": 1,
            "contractExcerpt": "逾期付款",
            "riskDesc": "付款违约责任",
            "suggestion": "补充违约金",
        }
    ]
}

_REVIEW_RESPONSE = {
    "summary": {
        "riskTotal": 1,
        "highRiskCount": 1,
        "mediumRiskCount": 0,
        "lowRiskCount": 0,
    },
    "riskItems": [
        {
            "seqNo": 1,
            "riskLevel": "HIGH",
            "riskScore": 0.95,
            "riskType": "付款责任",
            "clauseTitle": "逾期付款责任",
            "clausePosition": "[Page 1]",
            "pageNo": 1,
            "contractExcerpt": "逾期付款",
            "riskDesc": "付款违约责任",
            "suggestion": "补充违约金",
            "legalBasis": "《中华人民共和国民法典》合同编",
        }
    ],
}


def _request_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    return "\n".join(
        str(message.get("content") or "")
        for message in messages
        if isinstance(message, dict)
    )


def _response_for(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    text = _request_text(payload)
    review_markers = ("materialRiskCap", "highRiskCap", "draftCount", "review_context")
    if any(marker in text for marker in review_markers):
        return "review", _REVIEW_RESPONSE
    return "draft", _DRAFT_RESPONSE

@app.post("/v1/chat/completions")
async def completion(payload: dict[str, Any]):
    import json

    stage, response = _response_for(payload)
    calls.append({"model": str(payload.get("model") or ""), "stage": stage})
    content = json.dumps(response, ensure_ascii=False)
    return {"id": "e2e-mock", "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

@app.get("/test/metrics")
async def metrics():
    return {
        "requestCount": len(calls),
        "lastModel": calls[-1]["model"] if calls else None,
        "stages": [call["stage"] for call in calls],
    }

@app.post("/test/reset")
async def reset():
    calls.clear()
    return {"ok": True}
