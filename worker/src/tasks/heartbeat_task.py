"""worker 心跳任务：写 Redis key，healthcheck.sh 读取判活。"""
from __future__ import annotations

import os
import time

import redis

from worker_src.config.celery_app import celery_app

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


@celery_app.task(name="paritycheck.worker_heartbeat")
def worker_heartbeat() -> dict:
    timestamp = time.time()
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        client.set("paritycheck:worker:heartbeat", timestamp)
        return {"ok": True, "ts": timestamp}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
