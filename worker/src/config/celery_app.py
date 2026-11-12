"""worker 侧 Celery 应用：消费 paritycheck.run_recon_batch，beat 每 10s 写心跳。"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "paritycheck_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["worker_src.tasks.recon_task", "worker_src.tasks.heartbeat_task"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,
    task_acks_late=False,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "worker-heartbeat": {
            "task": "paritycheck.worker_heartbeat",
            "schedule": crontab(minute="*"),
        },
        "worker-heartbeat-fast": {
            "task": "paritycheck.worker_heartbeat",
            "schedule": 10.0,
        },
    },
)
