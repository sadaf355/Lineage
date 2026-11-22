"""Small Redis-backed worker for Phase 5. Run: python -m app.worker"""
from __future__ import annotations
import time, logging
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.phase56 import BackgroundJob
from app.services.jobs import run_job
settings=get_settings(); log=logging.getLogger("lineage.worker")

def main():
    if not settings.REDIS_URL:
        raise SystemExit("REDIS_URL is required for the worker")
    import redis
    r=redis.Redis.from_url(settings.REDIS_URL,decode_responses=True)
    log.info("LINEAGE worker started")
    last_retention=0.0
    last_sweep=0.0
    while True:
        now=time.time()
        if settings.RETENTION_PURGE_ENABLED and now-last_retention >= settings.RETENTION_PURGE_INTERVAL_HOURS*3600:
            dbm=SessionLocal()
            try:
                from app.services.jobs import enqueue
                enqueue(dbm,job_type="retention_purge",payload={})
            except Exception: log.exception("Could not schedule retention purge")
            finally: dbm.close()
            last_retention=now
        if settings.CAPTURE_SWEEP_ENABLED and now-last_sweep >= settings.CAPTURE_SWEEP_INTERVAL_HOURS*3600:
            dbm=SessionLocal()
            try:
                from app.services.jobs import enqueue
                enqueue(dbm,job_type="capture_sweep",payload={})
            except Exception: log.exception("Could not schedule capture sweep")
            finally: dbm.close()
            last_sweep=now
        item=r.blpop("lineage:jobs",timeout=max(1,int(settings.JOB_POLL_SECONDS)))
        if not item: continue
        job_id=item[1]; db=SessionLocal()
        try:
            job=db.get(BackgroundJob,job_id)
            if job and job.status=="queued": run_job(db,job)
        except Exception: log.exception("Job %s failed",job_id)
        finally: db.close()

if __name__=="__main__": main()
