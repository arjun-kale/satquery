"""The explicit job state machine used by every analysis request."""

from enum import StrEnum


class JobStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    ROUTING = "ROUTING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class InvalidJobTransition(ValueError):
    """Raised when a caller attempts to skip or leave a terminal state."""


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.RECEIVED: {JobStatus.VALIDATED, JobStatus.REJECTED, JobStatus.FAILED},
    JobStatus.VALIDATED: {JobStatus.ROUTING, JobStatus.REJECTED, JobStatus.FAILED},
    JobStatus.ROUTING: {JobStatus.EXECUTING, JobStatus.REJECTED, JobStatus.FAILED},
    JobStatus.EXECUTING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.REJECTED: set(),
    JobStatus.FAILED: set(),
}


def validate_transition(current: JobStatus, target: JobStatus) -> None:
    """Reject every transition that is not explicitly represented above."""

    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidJobTransition(f"Cannot transition job from {current} to {target}.")
