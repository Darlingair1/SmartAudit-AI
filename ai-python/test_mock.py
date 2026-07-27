import argparse
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

callback_event = threading.Event()
callback_payload = {}


class MockCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        if self.path != "/mock/callback":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {"raw": body}

        global callback_payload
        callback_payload = data
        callback_event.set()

        resp = {"code": 200, "msg": "success", "data": {"ack": True}}
        resp_bytes = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)


def start_mock_server(host: str, port: int) -> HTTPServer:
    server = HTTPServer((host, port), MockCallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def main():
    parser = argparse.ArgumentParser(description="Mock test for SmartAudit AI service")
    parser.add_argument("--pdf", required=True, help="Absolute path to local PDF file")
    parser.add_argument("--ai-url", default="http://127.0.0.1:8000/internal/v1/ai/audit/jobs")
    parser.add_argument("--callback-host", default="127.0.0.1")
    parser.add_argument("--callback-port", type=int, default=18080)
    parser.add_argument("--wait-seconds", type=int, default=240)
    parser.add_argument("--model-name", default=os.getenv("LLM_MODEL", "deepseek-v4-flash"))
    args = parser.parse_args()

    pdf_path = str(Path(args.pdf).resolve())
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    server = start_mock_server(args.callback_host, args.callback_port)
    callback_url = f"http://{args.callback_host}:{args.callback_port}/mock/callback"
    print(f"[1/3] Mock callback server started: {callback_url}")

    payload = {
        "taskId": str(10_000_000_000_000 + uuid.uuid4().int % 100_000),
        "taskNo": f"AT_TEST_{uuid.uuid4().hex[:8].upper()}",
        "filePath": pdf_path,
        "fileName": Path(pdf_path).name,
        "callbackUrl": callback_url,
        "callbackToken": "mock-token",
        "modelName": args.model_name,
        "ruleSetCodes": ["PENALTY", "PAYMENT_TERM", "TERMINATION"],
        "traceId": f"trace-{uuid.uuid4().hex[:10]}",
    }

    print(f"[2/3] Submit audit request to: {args.ai_url}")
    submit_resp = requests.post(args.ai_url, json=payload, timeout=15)
    print(f"Submit status: {submit_resp.status_code}")
    print(f"Submit body  : {submit_resp.text}")

    if submit_resp.status_code >= 300:
        server.shutdown()
        return

    print(f"[3/3] Waiting callback for up to {args.wait_seconds}s ...")
    received = callback_event.wait(timeout=args.wait_seconds)
    if not received:
        print("No callback received within timeout.")
    else:
        print("Callback received:")
        print(json.dumps(callback_payload, ensure_ascii=False, indent=2))

    server.shutdown()


if __name__ == "__main__":
    main()
