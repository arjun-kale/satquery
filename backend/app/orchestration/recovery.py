"""Startup recovery: runs that were in flight when the process died can never finish.

Without this, a job killed mid-step (e.g. an out-of-memory restart) stays "EXECUTING" forever and
the UI waits on it indefinitely. At startup nothing is running, so every non-terminal job is marked
FAILED, and any step still marked RUNNING in its trace is marked FAILED with the reason. The UI
then shows the failure with a Retry button.
"""

from __future__ import annotations

import datetime
import json
import logging

from app.state import JobStatus
from app.storage.artifacts import ArtifactRepository
from app.storage.jobs import JobRepository

log = logging.getLogger("satquery.recovery")

INTERRUPTED = "INTERRUPTED: the server restarted during this run"


def fail_interrupted_jobs(job_repo: JobRepository, artifact_repo: ArtifactRepository) -> int:
    count = 0
    for job in job_repo.unfinished():
        if artifact_repo.artifact_exists(job.id, "trace.json"):
            path = artifact_repo.artifact_path(job.id, "trace.json")
            saved = json.loads(path.read_text())
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for step in saved["trace"].get("steps", []):
                if step.get("status") == "RUNNING":
                    step["status"] = "FAILED"
                    step["error"] = "Interrupted: the server restarted while this step was running."
                    step["end_time"] = now
            path.write_text(json.dumps(saved))
        job_repo.transition(job.id, JobStatus.FAILED, failure_reason=INTERRUPTED)
        count += 1
    if count:
        log.warning("marked %d interrupted job(s) as failed", count)
    return count
