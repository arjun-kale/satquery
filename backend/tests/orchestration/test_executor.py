import pytest
from backend.app.orchestration.router import QueryRouter
from backend.app.orchestration.executor import DAGExecutor
from backend.app.storage.jobs import JobRepository
from backend.app.state import JobStatus
import tempfile
import pathlib

@pytest.fixture
def job_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = pathlib.Path(tmpdir) / "test.db"
        repo = JobRepository(db_path)
        repo.initialize()
        yield repo

@pytest.fixture(scope="module")
def router():
    return QueryRouter("all-MiniLM-L6-v2")

@pytest.fixture
def executor(router, job_repo):
    return DAGExecutor(router, job_repo)

def test_executor_supported_query(executor, job_repo):
    job = job_repo.create()
    job_id = job.id
    
    trace = executor.execute(job_id, "calculate water index", {"image_id": "123"})
    
    assert trace.job_id == job_id
    assert trace.trace.canonical_template_id == "SPECTRAL_WATER_VEGETATION"
    assert trace.trace.similarity_score > 0.60
    assert trace.trace.total_latency_ms is not None
    assert len(trace.trace.steps) == 4
    
    for step in trace.trace.steps:
        assert step.status == "SUCCESS"
        assert "mock_result" in step.outputs
        
    job = job_repo.get(job_id)
    assert job.status == JobStatus.COMPLETED

def test_executor_unsupported_query(executor, job_repo):
    job = job_repo.create()
    job_id = job.id
    
    trace = executor.execute(job_id, "order a pizza", {"image_id": "123"})
    
    assert trace.job_id == job_id
    assert trace.trace.canonical_template_id is None
    assert len(trace.trace.steps) == 0
    
    job = job_repo.get(job_id)
    assert job.status == JobStatus.REJECTED

def test_executor_tool_failure(executor, job_repo):
    job = job_repo.create()
    job_id = job.id
    
    # We pass fail_compatibility to trigger a simulated failure in the change detection DAG
    trace = executor.execute(job_id, "what has changed between these two images", {"fail_compatibility": True})
    
    assert trace.job_id == job_id
    assert trace.trace.canonical_template_id == "CHANGE_DETECTION"
    
    # It should fail at the first step (compatibility)
    assert len(trace.trace.steps) == 1
    assert trace.trace.steps[0].tool_name == "compatibility"
    assert trace.trace.steps[0].status == "FAILED"
    assert "Compatibility check failed" in trace.trace.steps[0].error
    
    job = job_repo.get(job_id)
    assert job.status == JobStatus.FAILED
