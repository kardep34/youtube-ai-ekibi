from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from job_queue import JobQueue
from queue_api import create_server
from queue_worker import run_once


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup((workspace := TemporaryDirectory()).cleanup)
        self.path = Path(workspace.name) / "queue.sqlite"
        self.queue = JobQueue(self.path)
        self.token = "local-test-" + "x" * 32
        server = create_server(self.queue, self.token, ("127.0.0.1", 0))
        self.addCleanup(server.server_close)
        Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.port = server.server_port
        self.task = {"title": "Kara Deliğe Düşersen Ne Olur?", "brief": "Türkçe açılış."}

    def http(self, method, path, payload=None, *, token=True, key="documentary-001"):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            headers = {"Content-Type": "application/json", "Idempotency-Key": key}
            if token:
                headers["Authorization"] = "Bearer " + self.token
            conn.request(method, path, json.dumps(payload) if payload is not None else None, headers)
            reply = conn.getresponse()
            return reply.status, json.loads(reply.read())
        finally:
            conn.close()

    def test_authenticated_http_to_worker_to_status(self):
        status, created = self.http("POST", "/jobs", self.task)
        self.assertEqual(status, 200)
        job_id = created["id"]
        self.assertEqual(self.http("GET", "/jobs/" + job_id)[1]["status"], "queued")
        self.assertTrue(run_once(self.queue, lambda task: {"output": task["title"]}))
        _, job = self.http("GET", "/jobs/" + job_id)
        self.assertEqual((job["status"], job["attempt"], job["result"]),
                         ("succeeded", 1, {"output": self.task["title"]}))
        self.assertFalse(run_once(self.queue, lambda task: self.fail("duplicate run")))

    def test_unauthorized_and_malformed_submissions(self):
        self.assertEqual(self.http("POST", "/jobs", self.task, token=False)[0], 401)
        self.assertEqual(self.http("POST", "/jobs", {"title": "a"})[0], 400)
        self.assertEqual(self.http("POST", "/jobs", self.task, key="short")[0], 400)
        self.assertIsNone(self.queue.claim())

    def test_concurrent_duplicates_and_payload_conflicts(self):
        with ThreadPoolExecutor(4) as pool:
            ids = list(pool.map(lambda _: self.http("POST", "/jobs", self.task)[1]["id"],
                                range(8)))
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(self.http("POST", "/jobs", {**self.task, "brief": "Farklı"})[0], 409)

    def test_concurrent_workers_and_wrong_completion_token(self):
        job_id = self.queue.submit("documentary-002", self.task)["id"]
        with ThreadPoolExecutor(4) as pool:
            claims = [x for x in pool.map(lambda _: self.queue.claim(), range(8)) if x]
        self.assertEqual(len(claims), 1)
        _, token, _ = claims[0]
        self.assertFalse(self.queue.finish(job_id, "wrong", True, {}))
        self.assertFalse(self.queue.retry_failed(job_id))
        self.assertTrue(self.queue.finish(job_id, token, True, {}))
        self.assertFalse(self.queue.finish(job_id, token, True, {}))

    def test_restart_persistence_and_controlled_retry(self):
        job_id = self.queue.submit("documentary-003", self.task)["id"]
        restarted = JobQueue(self.path)
        run_once(restarted, lambda task: {"errors": ["role"]})
        self.assertEqual(self.queue.get(job_id)["status"], "failed")
        self.assertTrue(restarted.retry_failed(job_id))
        self.assertFalse(restarted.retry_failed(job_id))
        run_once(restarted, lambda task: {"outputs": {"role": "ok"}})
        self.assertEqual(JobQueue(self.path).get(job_id)["attempt"], 2)
        self.assertEqual(restarted.get(job_id)["status"], "succeeded")
        self.assertFalse(restarted.retry_failed(job_id))


if __name__ == "__main__":
    unittest.main()
