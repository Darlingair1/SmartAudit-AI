import json

from fastapi.testclient import TestClient

from e2e_mock_llm import app


client = TestClient(app)


def _completion(prompt: str) -> dict:
    response = client.post(
        "/v1/chat/completions",
        json={"model": "e2e-mock", "messages": [{"role": "user", "content": prompt}]},
    )
    assert response.status_code == 200
    return json.loads(response.json()["choices"][0]["message"]["content"])


def setup_function() -> None:
    response = client.post("/test/reset")
    assert response.status_code == 200


def test_returns_draft_schema_for_agent1_request() -> None:
    payload = _completion("Return JSON with top-level draftRiskItems for this contract chunk")

    assert len(payload["draftRiskItems"]) == 1
    assert payload["draftRiskItems"][0]["contractExcerpt"] == "逾期付款"
    assert "riskItems" not in payload


def test_returns_final_schema_for_agent2_request() -> None:
    payload = _completion("draftCount=1, materialRiskCap=4, highRiskCap=2; return final JSON")

    assert payload["summary"]["riskTotal"] == 1
    assert len(payload["riskItems"]) == 1
    assert payload["riskItems"][0]["contractExcerpt"] == "逾期付款"
    assert "draftRiskItems" not in payload


def test_metrics_report_detected_pipeline_stages() -> None:
    _completion("Return draftRiskItems")
    _completion("draftCount=1 and materialRiskCap=4")

    metrics = client.get("/test/metrics").json()
    assert metrics == {
        "requestCount": 2,
        "lastModel": "e2e-mock",
        "stages": ["draft", "review"],
    }
