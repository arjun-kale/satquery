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
    # The whole DAG is recorded up front; execution stops at the first failed step
    # (here: preview, because no image was supplied).
    assert trace.trace.planned_steps == ["preview", "spectral_index", "geochat_vqa", "geodesy"]
    assert [s.tool_name for s in trace.trace.steps] == ["preview"]
    assert trace.trace.steps[0].status == "FAILED"

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


def _named_geotiff(path, bands=("B04", "B03", "B02", "B08"), epsg=32643, size=64):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    rng = np.random.default_rng(0)
    with rasterio.open(
        path, "w", driver="GTiff", width=size, height=size, count=len(bands), dtype="uint16",
        crs=f"EPSG:{epsg}", transform=from_origin(700000, 1400000, 10, 10),
    ) as ds:
        for i, name in enumerate(bands, start=1):
            data = rng.integers(500, 1500, (size, size), dtype="uint16")
            if name == "B08":
                data[:] = 2000
            if name == "B03":
                data[:, : size // 2] = 3000  # bright green on the left half → water by NDWI
            ds.write(data, i)
            ds.set_band_description(i, name)


def test_executor_water_question_uses_declared_bands(executor, job_repo, artifact_repo):
    _named_geotiff(artifact_repo.upload_path("img-a"))
    job = job_repo.create()

    trace = executor.execute(job.id, "calculate water index for this region", {"image_ids": ["img-a"]})

    steps = {s.tool_name: s for s in trace.trace.steps}
    out = steps["spectral_index"].outputs
    assert out["index_type"] == "NDWI"
    assert out["bands_used"] == {"green": "band 2 (B03)", "nir": "band 4 (B08)"}
    assert out["target_fraction"] == 0.5
    # 32 × 64 water pixels at 10 m × 10 m, derived from pixel counts only.
    assert out["target_area_m2"] == 32 * 64 * 100
    assert out["index_regions"][0]["area_m2"] == 32 * 64 * 100
    assert steps["geochat_vqa"].outputs["confidence_source"] == "unavailable"


def test_executor_index_fails_plainly_without_named_bands(executor, job_repo, artifact_repo):
    _named_geotiff(artifact_repo.upload_path("img-rgb"), bands=("", "", ""))
    job = job_repo.create()

    trace = executor.execute(job.id, "calculate water or vegetation index", {"image_ids": ["img-rgb"]})

    failed = trace.trace.steps[-1]
    assert failed.tool_name == "spectral_index"
    assert failed.status == "FAILED"
    assert "declares: none declared" in failed.error


def test_executor_change_pair_produces_regions_in_mock_mode(executor, job_repo, artifact_repo):
    _named_geotiff(artifact_repo.upload_path("t1"))
    _named_geotiff(artifact_repo.upload_path("t2"))
    job = job_repo.create()

    trace = executor.execute(
        job.id, "what changed", {"image_ids": ["t1", "t2"]}, scene_set_kind="bitemporal"
    )

    assert trace.trace.routing_mode == "scene_set_rule"
    assert trace.trace.similarity_score < 1.0  # the real similarity, not a forced 1.0
    steps = {s.tool_name: s for s in trace.trace.steps}
    assert all(s.status == "SUCCESS" for s in trace.trace.steps)
    assert steps["compatibility"].outputs == {"compatible": True}
    regions = steps["changeformer"].outputs["change_regions"]
    assert len(regions) == 1
    # Mock mask: 8×8 of 64×64 mask pixels over a 64×64 px, 10 m scene → one mask px = 100 m².
    assert regions[0]["area_m2"] == 64 * 100
    assert steps["change_area"].outputs["change_area_m2"] == 64 * 100


def test_executor_compatibility_rejects_crs_mismatch(executor, job_repo, artifact_repo):
    _named_geotiff(artifact_repo.upload_path("utm43"), epsg=32643)
    _named_geotiff(artifact_repo.upload_path("utm44"), epsg=32644)
    job = job_repo.create()

    trace = executor.execute(job.id, "what changed", {"image_ids": ["utm43", "utm44"]})

    assert trace.trace.steps[0].tool_name == "compatibility"
    assert "CRS_MISMATCH" in trace.trace.steps[0].error
    assert job_repo.get(job.id).status == JobStatus.FAILED


def test_executor_stops_before_next_step_when_cancelled(executor, job_repo):
    from app.orchestration.cancel import request_cancel
    from app.orchestration.executor import CANCELLED_REASON

    job = job_repo.create()
    request_cancel(job.id)

    trace = executor.execute(job.id, "calculate water index", {"image_ids": []})

    assert trace.trace.cancelled is True
    assert trace.trace.steps == []
    assert job_repo.get(job.id).failure_reason == CANCELLED_REASON
