"""A deliberately small SQLite repository for Phase 0 job state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.schemas import JobRecord
from app.state import JobStatus, validate_transition


class JobRepository:
    """Persist only state-machine data; imagery/artifacts are Phase 1 work."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN (
                        'RECEIVED', 'VALIDATED', 'ROUTING', 'EXECUTING',
                        'COMPLETED', 'REJECTED', 'FAILED'
                    )),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    failure_reason TEXT
                )
                """
            )

    def create(self) -> JobRecord:
        job_id = str(uuid4())
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs (id, status, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (job_id, JobStatus.RECEIVED.value, now, now),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, status, created_at, updated_at, failure_reason FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"No job exists with id {job_id}.")
        return JobRecord(
            id=row["id"],
            status=JobStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            failure_reason=row["failure_reason"],
        )

    def transition(
        self,
        job_id: str,
        target: JobStatus,
        *,
        failure_reason: str | None = None,
    ) -> JobRecord:
        existing = self.get(job_id)
        validate_transition(existing.status, target)
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, failure_reason = ? WHERE id = ?",
                (target.value, _utc_now(), failure_reason, job_id),
            )
        return self.get(job_id)

    def unfinished(self) -> list[JobRecord]:
        """Jobs not in a terminal state (only meaningful at startup, when nothing is running)."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM jobs WHERE status NOT IN ('COMPLETED', 'REJECTED', 'FAILED')"
            ).fetchall()
        return [self.get(r["id"]) for r in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
