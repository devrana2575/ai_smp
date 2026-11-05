"""Small in-process background-job manager for expensive research operations."""

from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobService:
    def __init__(
        self,
        state_dir: Optional[str] = None,
        max_workers: Optional[int] = None,
    ) -> None:
        self.state_dir = state_dir or settings.JOB_STATE_DIR
        os.makedirs(self.state_dir, exist_ok=True)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers or settings.JOB_MAX_WORKERS
        )
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _path(self, job_id: str) -> str:
        return os.path.join(self.state_dir, f"{job_id}.json")

    def _save(self, job: Dict[str, Any]) -> None:
        path = self._path(job["job_id"])
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(job, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)

    def submit(
        self,
        job_type: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._save(job)
        self._executor.submit(self._run, job_id, func, args, kwargs)
        return dict(job)

    def _run(
        self,
        job_id: str,
        func: Callable[..., Any],
        args: tuple,
        kwargs: dict,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "running"
            job["started_at"] = _now()
            self._save(job)
        try:
            result = func(*args, **kwargs)
            with self._lock:
                job["status"] = "completed"
                job["completed_at"] = _now()
                job["result"] = result
                self._save(job)
        except Exception as exc:  # noqa: BLE001 - job failure is returned
            with self._lock:
                job["status"] = "failed"
                job["completed_at"] = _now()
                job["error"] = f"{type(exc).__name__}: {exc}"
                self._save(job)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                path = self._path(job_id)
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as handle:
                        job = json.load(handle)
                    self._jobs[job_id] = job
            return dict(job) if job else None

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            jobs = sorted(
                self._jobs.values(),
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )
            return [dict(job) for job in jobs[:limit]]


job_service = JobService()
