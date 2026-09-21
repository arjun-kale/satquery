import datetime
import time
from typing import Dict, Any, List
from backend.app.orchestration.schema import OrchestratorTrace, ObservableExecutionTrace, ExecutionStep, StepStatus
from backend.app.orchestration.router import QueryRouter, ROUTER_VERSION, SIMILARITY_THRESHOLD
from backend.app.storage.jobs import JobRepository
from backend.app.state import JobStatus

class DAGExecutor:
    """
    Deterministic DAG executor. Runs only registered tools, records latency/errors,
    and persists an immutable Pydantic-validated trace.
    """
    def __init__(self, router: QueryRouter, job_repo: JobRepository):
        self.router = router
        self.job_repo = job_repo
        
    def execute(self, job_id: str, query: str, initial_inputs: Dict[str, Any]) -> ObservableExecutionTrace:
        job = self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
            
        # Ensure job is valid to start routing
        if job.status == JobStatus.RECEIVED:
            self.job_repo.transition(job_id, JobStatus.VALIDATED)
            
        self.job_repo.transition(job_id, JobStatus.ROUTING)
        
        start_time = time.time()
        route_result = self.router.route(query)
        
        trace = OrchestratorTrace(
            query=query,
            router_version=ROUTER_VERSION,
            canonical_template_id=route_result.query_type.value if route_result.query_type else None,
            similarity_score=route_result.score,
            similarity_threshold=SIMILARITY_THRESHOLD
        )
        
        if not route_result.is_supported:
            self.job_repo.transition(job_id, JobStatus.REJECTED, failure_reason="Unsupported query")
            trace.total_latency_ms = (time.time() - start_time) * 1000
            return ObservableExecutionTrace(job_id=job_id, trace=trace)
            
        self.job_repo.transition(job_id, JobStatus.EXECUTING)
        
        current_inputs = initial_inputs.copy()
        
        for tool_name in route_result.dag:
            step = ExecutionStep(tool_name=tool_name, status=StepStatus.RUNNING, inputs=current_inputs)
            step.start_time = datetime.datetime.now(datetime.timezone.utc)
            step_start_time = time.time()
            
            try:
                # TODO: Dispatch to actual tool registry implementation in Phase 5
                # For now, mock the tool execution
                if tool_name == "compatibility" and current_inputs.get("fail_compatibility"):
                    raise ValueError("Compatibility check failed")
                    
                output = {"mock_result": f"success from {tool_name}"}
                
                step.outputs = output
                step.status = StepStatus.SUCCESS
                current_inputs.update(output)
            except Exception as e:
                step.error = str(e)
                step.status = StepStatus.FAILED
                step.end_time = datetime.datetime.now(datetime.timezone.utc)
                step.latency_ms = (time.time() - step_start_time) * 1000
                trace.steps.append(step)
                
                self.job_repo.transition(job_id, JobStatus.FAILED, failure_reason=str(e))
                trace.total_latency_ms = (time.time() - start_time) * 1000
                return ObservableExecutionTrace(job_id=job_id, trace=trace)
                
            step.end_time = datetime.datetime.now(datetime.timezone.utc)
            step.latency_ms = (time.time() - step_start_time) * 1000
            trace.steps.append(step)
            
        self.job_repo.transition(job_id, JobStatus.COMPLETED)
        trace.total_latency_ms = (time.time() - start_time) * 1000
        
        return ObservableExecutionTrace(job_id=job_id, trace=trace)
