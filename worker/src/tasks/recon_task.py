"""分桶对账任务：与 backend 共用同一份 recon_engine 实现。"""
from __future__ import annotations

from src.services.recon_engine import run_batch
from src.utils.logger import get_logger
from worker_src.config.celery_app import celery_app

logger = get_logger("paritycheck.worker.recon")


@celery_app.task(name="paritycheck.run_recon_batch", bind=True, max_retries=1)
def run_recon_batch(self, batch_id: int) -> dict:
    logger.info("recon task start batch_id=%s task_id=%s", batch_id, self.request.id)
    result = run_batch(int(batch_id))
    logger.info("recon task done batch_id=%s result=%s", batch_id, result)
    return result
