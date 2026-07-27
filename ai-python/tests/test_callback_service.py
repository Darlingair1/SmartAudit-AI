import hashlib
import hmac
import os
import sys
import unittest
import asyncio
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(CURRENT_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from schemas.models import AuditCallbackPayload, CallbackSummary
from services.callback_service import _canonical_payload_json, _sign_payload, send_callback


class CallbackServiceTest(unittest.TestCase):

    def test_sign_payload_should_be_deterministic_with_fixed_time_and_nonce(self):
        body = '{"taskId":"1","status":"COMPLETED"}'
        secret = "test-secret-123"
        with patch("services.callback_service.time.time", return_value=1700000000), patch(
            "services.callback_service.uuid4"
        ) as mock_uuid:
            mock_uuid.return_value.hex = "abc123nonce"
            timestamp, nonce, signature = _sign_payload(body, secret)

        self.assertEqual("1700000000", timestamp)
        self.assertEqual("abc123nonce", nonce)

        expected = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}\n{nonce}\n{body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(expected, signature)

    def test_canonical_payload_json_should_not_be_empty(self):
        payload = AuditCallbackPayload(
            callbackId="cb_1",
            taskId="1",
            taskNo="T-1",
            pythonJobId="pyjob_1",
            status="COMPLETED",
            finishedAt="2026-01-01T00:00:00Z",
            summary=CallbackSummary(riskTotal=1, highRiskCount=1, mediumRiskCount=0, lowRiskCount=0),
            riskItems=[],
            error=None,
        )
        text = _canonical_payload_json(payload)
        self.assertIn('"callbackId":"cb_1"', text)
        self.assertIn('"status":"COMPLETED"', text)

    def test_callback_retries_server_error_then_succeeds(self):
        request = type("Request", (), {})()
        response_500 = type("Response", (), {"status_code": 500})()
        response_200 = type("Response", (), {"status_code": 200})()
        settings = type("Settings", (), {"callback_retry_times": 2, "callback_retry_interval_seconds": 0})()
        with patch("services.callback_service.get_settings", return_value=settings), patch(
            "services.callback_service._do_post_callback", side_effect=[response_500, response_200]
        ) as post:
            asyncio.run(send_callback(request, object()))
        self.assertEqual(2, post.call_count)

    def test_callback_raises_after_timeout_retries(self):
        request = type("Request", (), {})()
        settings = type("Settings", (), {"callback_retry_times": 2, "callback_retry_interval_seconds": 0})()
        with patch("services.callback_service.get_settings", return_value=settings), patch(
            "services.callback_service._do_post_callback", side_effect=TimeoutError("timeout")
        ) as post:
            with self.assertRaises(TimeoutError):
                asyncio.run(send_callback(request, object()))
        self.assertEqual(2, post.call_count)


if __name__ == "__main__":
    unittest.main()
