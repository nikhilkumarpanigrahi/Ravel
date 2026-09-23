"""Asynchronous Investigation Task Manager for RAVEL.

Enables background execution of heavy forensic graph traversals and LLM syntheses,
providing immediate 202 Accepted responses with real-time task polling.
"""

from __future__ import annotations

import datetime as dt
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class InvestigationTask:
    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))
    completed_at: dt.datetime | None = None
    progress_stage: str = "QUEUED"
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        elapsed_s = None
        if self.completed_at:
            elapsed_s = round((self.completed_at - self.created_at).total_seconds(), 2)
        elif self.status == TaskStatus.RUNNING:
            elapsed_s = round((dt.datetime.now(dt.UTC) - self.created_at).total_seconds(), 2)

        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": elapsed_s,
            "progress_stage": self.progress_stage,
            "result": self.result,
            "error": self.error,
        }


class TaskRunner:
    """Thread-safe background task runner for investigations."""

    def __init__(self):
        self._tasks: dict[str, InvestigationTask] = {}
        self._lock = threading.Lock()

    def submit(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> InvestigationTask:
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        task = InvestigationTask(task_id=task_id, name=name)
        with self._lock:
            self._tasks[task_id] = task

        def _worker():
            with self._lock:
                task.status = TaskStatus.RUNNING
                task.progress_stage = "PROCESSING_INVESTIGATION"

            try:
                res = func(*args, **kwargs)
                if hasattr(res, "model_dump"):
                    res = res.model_dump(mode="json")
                with self._lock:
                    task.status = TaskStatus.COMPLETED
                    task.progress_stage = "FINISHED"
                    task.result = res
                    task.completed_at = dt.datetime.now(dt.UTC)
            except Exception as exc:
                with self._lock:
                    task.status = TaskStatus.FAILED
                    task.progress_stage = "ERROR"
                    task.error = str(exc)
                    task.completed_at = dt.datetime.now(dt.UTC)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return task

    def get(self, task_id: str) -> InvestigationTask | None:
        with self._lock:
            return self._tasks.get(task_id)


task_runner = TaskRunner()
