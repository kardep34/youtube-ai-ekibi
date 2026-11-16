"""Task intake and status API. Serve behind HTTPS for remote clients."""

from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re

from job_queue import JobQueue, QueueConflict


def validate(payload):
    if not isinstance(payload, dict) or set(payload) != {"title", "brief"}:
        raise ValueError("title ve brief alanları gerekli.")
    limits = {"title": 200, "brief": 6000}
    if any(not isinstance(payload[k], str) or not 0 < len(payload[k].strip()) <= limit
           for k, limit in limits.items()):
        raise ValueError("Görev başlığı veya metni geçersiz.")
    return {key: value.strip() for key, value in payload.items()}


def create_server(queue, secret, address=("127.0.0.1", 8765)):
    if len(secret) < 32 or not secret.isascii():
        raise ValueError("VORTEX_QUEUE_TOKEN en az 32 ASCII karakter olmalı.")
    expected = ("Bearer " + secret).encode()

    class Handler(BaseHTTPRequestHandler):
        timeout = 10

        def send_json(self, status, data):
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            value = self.headers.get("Authorization", "").encode("utf-8")
            if compare_digest(value, expected):
                return True
            self.send_json(401, {"error": "Yetkilendirme gerekli."})
            return False

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/jobs":
                self.send_json(404, {"error": "Yol bulunamadı."})
                return
            key = self.headers.get("Idempotency-Key", "")
            try:
                if not re.fullmatch(r"[A-Za-z0-9_.:-]{12,128}", key):
                    raise ValueError("Geçerli Idempotency-Key gerekli.")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("application/json gerekli.")
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 40000:
                    raise ValueError("Görev gövdesi eksik veya çok büyük.")
                payload = validate(json.loads(self.rfile.read(size)))
                self.send_json(200, queue.submit(key, payload))
            except QueueConflict as exc:
                self.send_json(409, {"error": str(exc)})
            except (ValueError, TimeoutError):
                self.send_json(400, {"error": "Geçersiz görev isteği."})

        def do_GET(self):
            if not self.authorized():
                return
            match = re.fullmatch(r"/jobs/([a-f0-9]{32})", self.path)
            job = queue.get(match[1]) if match else None
            self.send_json(200 if job else 404, job or {"error": "Görev bulunamadı."})

        def log_message(self, *args):
            return

    return ThreadingHTTPServer(address, Handler)


if __name__ == "__main__":
    queue = JobQueue(os.environ["VORTEX_QUEUE_DB"])
    with create_server(queue, os.environ["VORTEX_QUEUE_TOKEN"]) as server:
        server.serve_forever()
