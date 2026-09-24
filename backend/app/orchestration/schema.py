import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

class ExecutionStep(BaseModel):
    tool_name: str
    status: StepStatus = StepStatus.PENDING
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    latency_ms: Optional[float] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

TRACE_SCHEMA_VERSION = "1.1"


class RouteCandidate(BaseModel):
    task: str
    score: float


class OrchestratorTrace(BaseModel):
    query: str
    router_version: str
    canonical_template_id: Optional[str] = None
    similarity_score: Optional[float] = None
    similarity_threshold: float
    routing_mode: str = "similarity"
    runner_up: Optional[RouteCandidate] = None
    candidates: List[RouteCandidate] = Field(default_factory=list)
    rejection: Optional[str] = None
    scene_set_kind: Optional[str] = None
    image_ids: List[str] = Field(default_factory=list)
    model_mode: Optional[str] = None
    # The router's fixed DAG, known before the first step runs.
    planned_steps: List[str] = Field(default_factory=list)
    cancelled: bool = False
    steps: List[ExecutionStep] = Field(default_factory=list)
    total_latency_ms: Optional[float] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class ObservableExecutionTrace(BaseModel):
    schema_version: str = TRACE_SCHEMA_VERSION
    job_id: str
    trace: OrchestratorTrace
