"""Persistent single-host queue backed by SQLite on a durable local volume."""

from contextlib import closing
from hashlib import sha256
import json
import sqlite3
import uuid


class QueueConflict(ValueError):
    pass


class JobQueue:
    def __init__(self, path):
        self.path = path
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    request_key TEXT NOT NULL UNIQUE,
                    digest TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('queued', 'running', 'succeeded', 'failed')
                    ),
                    attempt INTEGER NOT NULL DEFAULT 0,
                    run_token TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def submit(self, key, payload):
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        digest = sha256(encoded.encode()).hexdigest()
        with closing(self.connect()) as db, db:
            db.execute(
                "INSERT INTO jobs (id, request_key, digest, payload, status) "
                "VALUES (?, ?, ?, ?, 'queued') ON CONFLICT(request_key) DO NOTHING",
                (uuid.uuid4().hex, key, digest, encoded),
            )
            row = db.execute(
                "SELECT id, status, digest FROM jobs WHERE request_key=?", (key,)
            ).fetchone()
            if row["digest"] != digest:
                raise QueueConflict("Bu istek anahtarı farklı bir görev için kullanıldı.")
            return {"id": row["id"], "status": row["status"]}

    def get(self, job_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT id, status, attempt, payload, result, created_at, updated_at "
                "FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        job = dict(row)
        job["payload"] = json.loads(job["payload"])
        job["result"] = json.loads(job["result"]) if job["result"] else None
        return job

    def claim(self):
        token = uuid.uuid4().hex
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id, payload FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='running', attempt=attempt+1, run_token=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (token, row["id"]),
            )
            return row["id"], token, json.loads(row["payload"])

    def finish(self, job_id, token, success, result):
        with closing(self.connect()) as db, db:
            return db.execute(
                "UPDATE jobs SET status=?, result=?, run_token=NULL, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='running' AND run_token=?",
                ("succeeded" if success else "failed", json.dumps(result, ensure_ascii=False),
                 job_id, token),
            ).rowcount == 1

    def retry_failed(self, job_id):
        with closing(self.connect()) as db, db:
            return db.execute(
                "UPDATE jobs SET status='queued', result=NULL, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND status='failed'", (job_id,)
            ).rowcount == 1
