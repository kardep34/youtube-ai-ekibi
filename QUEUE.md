# VORTEX 360 task queue

Run queue_api.py and queue_worker.py as separate processes on one host. Both
must use the same VORTEX_QUEUE_DB file on a durable local volume. Set a random
VORTEX_QUEUE_TOKEN of at least 32 ASCII characters for the API. Set
GEMINI_API_KEY only for the worker. The API binds loopback. For remote clients
put it behind a TLS reverse proxy on the same host. Restrict access to authorized
clients. Set VORTEX_QUEUE_URL and VORTEX_QUEUE_TOKEN in Streamlit secrets to
enable panel intake and status.

POST /jobs takes JSON {"title":"…","brief":"…"}, an Authorization Bearer
header and an Idempotency-Key header. Reuse exactly the same key for delivery
retries. GET /jobs/{id} retrieves status and result. Submit only through
an authenticated tool or through the signed-in Streamlit queue form.

Worker claims are transactional. A failed attempt can be explicitly requeued
with python queue_worker.py --retry-failed JOB_ID. A process interrupted during
a provider request leaves the job running for operator review, because an
automatic rerun could duplicate a billable call. The worker only invokes
the existing five text bots. Narration remains in the Streamlit voice panel.

Run queue tests with python -m unittest -v test_job_queue.
