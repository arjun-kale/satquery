"""DAGExecutor — runs the routed DAG, persists observable trace."""
from __future__ import annotations

import datetime
import json
import time
from typing import Any

from app.orchestration.cancel import clear as cancel_clear, is_cancel_requested
from app.orchestration.router import QueryRouter, QueryType, ROUTER_VERSION, SIMILARITY_THRESHOLD
from app.orchestration.schema import (
    ExecutionStep,
    RouteCandidate,
    ObservableExecutionTrace,
    OrchestratorTrace,
    StepStatus,
)
from app.state import JobStatus
from app.storage.artifacts import ArtifactRepository
from app.storage.jobs import JobRepository

CANCELLED_REASON = "CANCELLED: stopped by the user"


class DAGExecutor:
    """
    Deterministic DAG executor.

    Runs only registered tools, records latency/errors per step,
    persists an immutable trace to the ArtifactRepository after every
    state change so the frontend can poll live progress.
    """

    def __init__(
        self,
        router: QueryRouter,
        job_repo: JobRepository,
        artifact_repo: ArtifactRepository,
        model_mode: str = "mock",
    ) -> None:
        self.router = router
        self.job_repo = job_repo
        self.artifact_repo = artifact_repo
        self.model_mode = model_mode

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_trace(self, job_id: str, trace_obj: ObservableExecutionTrace) -> None:
        path = self.artifact_repo.artifact_path(job_id, "trace.json")
        path.write_text(trace_obj.model_dump_json())

    # ------------------------------------------------------------------
    # Main entry point (called from BackgroundTasks)
    # ------------------------------------------------------------------

    def execute(
        self,
        job_id: str,
        query: str,
        initial_inputs: dict[str, Any],
        scene_set_kind: str | None = None,
        forced_task: str | None = None,
    ) -> ObservableExecutionTrace:
        """Run the full DAG for *job_id* and return the final trace."""
        from app.orchestration.dispatcher import dispatch_tool

        # --- State: RECEIVED → VALIDATED → ROUTING ---
        job = self.job_repo.get(job_id)
        if job.status == JobStatus.RECEIVED:
            self.job_repo.transition(job_id, JobStatus.VALIDATED)
        self.job_repo.transition(job_id, JobStatus.ROUTING)

        start_time = time.time()

        # Inject query into inputs so VQA nodes can access it
        initial_inputs = {**initial_inputs, "query": query}

        # --- Route ---
        route_result = self.router.route(
            query,
            image_ids=initial_inputs.get("image_ids"),
            scene_set_kind=scene_set_kind,
            forced_type=QueryType(forced_task) if forced_task else None,
        )

        trace = OrchestratorTrace(
            query=query,
            router_version=ROUTER_VERSION,
            canonical_template_id=(
                route_result.query_type.value if route_result.query_type else None
            ),
            similarity_score=route_result.score,
            similarity_threshold=SIMILARITY_THRESHOLD,
            routing_mode=route_result.mode,
            runner_up=(
                RouteCandidate(task=route_result.runner_up.task.value, score=route_result.runner_up.score)
                if route_result.runner_up else None
            ),
            candidates=[RouteCandidate(task=c.task.value, score=c.score) for c in route_result.candidates],
            rejection=route_result.rejection,
            scene_set_kind=scene_set_kind,
            image_ids=list(initial_inputs.get("image_ids") or []),
            model_mode=self.model_mode,
            planned_steps=list(route_result.dag),
        )
        trace_obj = ObservableExecutionTrace(job_id=job_id, trace=trace)
        self._save_trace(job_id, trace_obj)

        if not route_result.is_supported:
            self.job_repo.transition(
                job_id, JobStatus.REJECTED,
                failure_reason=f"Unsupported query ({route_result.rejection or 'no route'})",
            )
            trace.total_latency_ms = (time.time() - start_time) * 1000
            self._save_trace(job_id, trace_obj)
            return trace_obj

        # --- Execute DAG ---
        self.job_repo.transition(job_id, JobStatus.EXECUTING)
        current_inputs = initial_inputs.copy()

        for tool_name in route_result.dag:
            if is_cancel_requested(job_id):
                cancel_clear(job_id)
                trace.cancelled = True
                self.job_repo.transition(job_id, JobStatus.FAILED, failure_reason=CANCELLED_REASON)
                trace.total_latency_ms = (time.time() - start_time) * 1000
                self._save_trace(job_id, trace_obj)
                return trace_obj

            step = ExecutionStep(
                tool_name=tool_name,
                status=StepStatus.RUNNING,
                inputs=current_inputs,
            )
            step.start_time = datetime.datetime.now(datetime.timezone.utc)
            step_start = time.time()

            trace.steps.append(step)
            self._save_trace(job_id, trace_obj)

            try:
                output = dispatch_tool(
                    tool_name,
                    current_inputs,
                    self.artifact_repo,
                    job_id,
                    model_mode=self.model_mode,
                )
                step.outputs = output
                step.status = StepStatus.SUCCESS
                current_inputs.update(output)

            except Exception as exc:  # noqa: BLE001
                step.error = str(exc)
                step.status = StepStatus.FAILED
                step.end_time = datetime.datetime.now(datetime.timezone.utc)
                step.latency_ms = (time.time() - step_start) * 1000

                self.job_repo.transition(
                    job_id, JobStatus.FAILED, failure_reason=str(exc)
                )
                trace.total_latency_ms = (time.time() - start_time) * 1000
                self._save_trace(job_id, trace_obj)
                return trace_obj

            step.end_time = datetime.datetime.now(datetime.timezone.utc)
            step.latency_ms = (time.time() - step_start) * 1000
            self._save_trace(job_id, trace_obj)

        cancel_clear(job_id)
        self.job_repo.transition(job_id, JobStatus.COMPLETED)
        trace.total_latency_ms = (time.time() - start_time) * 1000
        self._save_trace(job_id, trace_obj)
        return trace_obj
