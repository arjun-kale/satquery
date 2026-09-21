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

class OrchestratorTrace(BaseModel):
    query: str
    router_version: str
    canonical_template_id: Optional[str] = None
    similarity_score: Optional[float] = None
    similarity_threshold: float
    steps: List[ExecutionStep] = Field(default_factory=list)
    total_latency_ms: Optional[float] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class ObservableExecutionTrace(BaseModel):
    job_id: str
    trace: OrchestratorTrace
