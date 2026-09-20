import pytest

from app.state import InvalidJobTransition, JobStatus, validate_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.RECEIVED, JobStatus.VALIDATED),
        (JobStatus.RECEIVED, JobStatus.REJECTED),
        (JobStatus.RECEIVED, JobStatus.FAILED),
        (JobStatus.VALIDATED, JobStatus.ROUTING),
        (JobStatus.ROUTING, JobStatus.EXECUTING),
        (JobStatus.EXECUTING, JobStatus.COMPLETED),
        (JobStatus.EXECUTING, JobStatus.FAILED),
    ],
)
def test_allowed_transitions(current: JobStatus, target: JobStatus) -> None:
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.RECEIVED, JobStatus.COMPLETED),
        (JobStatus.VALIDATED, JobStatus.EXECUTING),
        (JobStatus.COMPLETED, JobStatus.FAILED),
        (JobStatus.REJECTED, JobStatus.ROUTING),
        (JobStatus.FAILED, JobStatus.RECEIVED),
    ],
)
def test_illegal_transitions_are_rejected(current: JobStatus, target: JobStatus) -> None:
    with pytest.raises(InvalidJobTransition):
        validate_transition(current, target)
