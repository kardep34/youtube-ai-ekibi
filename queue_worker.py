"""Run queued tasks without loading Streamlit or YouTube credentials."""

import argparse
import os
import time

from job_queue import JobQueue


def run_once(queue, execute):
    claimed = queue.claim()
    if claimed is None:
        return False
    job_id, token, task = claimed
    try:
        result = execute(task)
    except Exception:
        result = {"error": "Görev çalıştırılamadı."}
    queue.finish(job_id, token, not bool(result.get("errors") or result.get("error")), result)
    return True


def run_bots(client, task):
    from bot_runtime import bot_calistir, botlar

    results, failures = {}, []
    topic = f"{task['title']}\n\n{task['brief']}"
    for role, instructions in botlar.items():
        try:
            results[role] = bot_calistir(client, instructions, topic)
        except Exception:
            failures.append(role)
    return {"outputs": results, "errors": failures}


if __name__ == "__main__":
    from google import genai

    parser = argparse.ArgumentParser()
    parser.add_argument("--retry-failed")
    args = parser.parse_args()
    queue = JobQueue(os.environ["VORTEX_QUEUE_DB"])
    if args.retry_failed:
        if not queue.retry_failed(args.retry_failed):
            parser.exit(1, "Yalnızca başarısız görevler yeniden kuyruğa alınabilir.\n")
    else:
        with genai.Client(api_key=os.environ["GEMINI_API_KEY"]) as client:
            while True:
                if not run_once(queue, lambda task: run_bots(client, task)):
                    time.sleep(2)
