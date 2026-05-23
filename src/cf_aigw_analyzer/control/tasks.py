"""In-process async sync-job registry.

We do not need a queue / Celery for an analyzer-grade workload: the only
operations are user-triggered ``sync`` / ``sync-usage`` calls. The registry
tracks runs by a job_id string, exposes status snapshots, and propagates the
resulting ``sync_runs.run_id`` so the frontend can drill in.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from cf_aigw_analyzer.utils.time import utc_now


@dataclass(slots=True)
class SyncJob:
    job_id: str
    mode: str
    started_at: str
    status: str = "running"
    finished_at: str | None = None
    logs_count: int = 0
    usage_fetched: int = 0
    usage_parsed: int = 0
    usage_no_usage: int = 0
    usage_failed: int = 0
    targets: int = 0
    error: str | None = None
    run_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "logs_count": self.logs_count,
            "usage_fetched": self.usage_fetched,
            "usage_parsed": self.usage_parsed,
            "usage_no_usage": self.usage_no_usage,
            "usage_failed": self.usage_failed,
            "targets": self.targets,
            "error": self.error,
            "run_id": self.run_id,
        }


class JobRegistry:
    """Track in-flight and recently completed sync jobs."""

    def __init__(self, retention: int = 100) -> None:
        self._jobs: dict[str, SyncJob] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()
        self._retention = retention

    def create(self, mode: str) -> SyncJob:
        job_id = uuid.uuid4().hex[:12]
        job = SyncJob(job_id=job_id, mode=mode, started_at=utc_now())
        self._jobs[job_id] = job
        self._trim()
        return job

    def attach(self, job_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks[job_id] = task

    def get(self, job_id: str) -> SyncJob | None:
        return self._jobs.get(job_id)

    def list(self) -> list[SyncJob]:
        return list(self._jobs.values())

    def mark_done(self, job_id: str, **fields: Any) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        job.status = "failed" if fields.get("error") else "done"
        job.finished_at = utc_now()
        self._tasks.pop(job_id, None)
        self._trim()

    def _trim(self) -> None:
        if len(self._jobs) <= self._retention:
            return
        # Drop oldest finished jobs first
        sorted_jobs = sorted(self._jobs.values(), key=lambda j: (j.status != "done", j.started_at))
        to_drop = len(self._jobs) - self._retention
        for job in sorted_jobs[:to_drop]:
            self._jobs.pop(job.job_id, None)
