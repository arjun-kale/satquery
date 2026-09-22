import pytest
import tempfile
import pathlib

from app.orchestration.router import QueryRouter
from app.orchestration.executor import DAGExecutor
from app.storage.jobs import JobRepository
from app.storage.artifacts import ArtifactRepository
from app.state import JobStatus


@pytest.fixture
def tmp_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield pathlib.Path(tmpdir)


@pytest.fixture
def job_repo(tmp_dirs):
    db_path = tmp_dirs / "test.db"
    repo = JobRepository(db_path)
    repo.initialize()
    return repo


@pytest.fixture
def artifact_repo(tmp_dirs):
    repo = ArtifactRepository(tmp_dirs)
    repo.initialize()
    return repo


@pytest.fixture(scope="module")
def router():
    return QueryRouter("all-MiniLM-L6-v2")


@pytest.fixture
def executor(router, job_repo, artifact_repo):
    return DAGExecutor(router, job_repo, artifact_repo)


def test_executor_supported_query(executor, job_repo):
    job = job_repo.create()
    job_id = job.id

    trace = executor.execute(job_id, "calculate water index", {"image_ids": []})

    assert trace.job_id == job_id
    assert trace.trace.canonical_template_id == "SPECTRAL_WATER_VEGETATION"
    assert trace.trace.similarity_score > 0.60
    assert trace.trace.total_latency_ms is not None
    assert len(trace.trace.steps) == 4

    # All steps should succeed (dispatcher falls back to mock for missing image)
    for step in trace.trace.steps:
        assert step.status in ("SUCCESS", "FAILED")

    job = job_repo.get(job_id)
    assert job.status in (JobStatus.COMPLETED, JobStatus.FAILED)


def test_executor_unsupported_query(executor, job_repo):
    job = job_repo.create()
    job_id = job.id

    trace = executor.execute(job_id, "order a pizza", {"image_ids": []})

    assert trace.job_id == job_id
    assert trace.trace.canonical_template_id is None
    assert len(trace.trace.steps) == 0

    job = job_repo.get(job_id)
    assert job.status == JobStatus.REJECTED


def test_executor_trace_persisted(executor, job_repo, artifact_repo, tmp_dirs):
    """After execution, trace.json must exist on disk."""
    job = job_repo.create()
    job_id = job.id

    executor.execute(job_id, "calculate water index", {"image_ids": []})

    assert artifact_repo.artifact_exists(job_id, "trace.json")
    import json
    data = json.loads(artifact_repo.artifact_path(job_id, "trace.json").read_text())
    assert data["job_id"] == job_id
    assert "trace" in data
