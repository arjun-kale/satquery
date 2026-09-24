"""POST /api/chat — an analysis streamed with the Vercel AI SDK UI Message Stream protocol (v1).

The frontend's ``useChat`` (``DefaultChatTransport``) posts ``{id, messages, trigger, messageId}``
plus the scene set in ``body``. The last user message's text is the question. The same
DAGExecutor as ``POST /api/jobs`` runs in a worker thread; every trace write it makes becomes
stream parts, so the client sees each real state change as it happens:

    start                      message metadata: jobId, localId
    data-job                   {jobId, localId}
    data-trace (id = jobId)    the full recorded trace, replaced in place on every update
    tool-input-available       a step started (dynamic tool, real tool name and inputs)
    tool-output-available      a step finished, with its real outputs
    tool-output-error          a step failed, with its error
    text-start/-delta/-end     the model's answer text, sent once it exists (not token-streamed)
    finish, [DONE]

No reasoning parts are emitted: the pipeline produces no model reasoning text. If the client
disconnects (useChat ``stop()``), the job is asked to cancel before its next step.
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.api.jobs import query_router
from app.orchestration.cancel import request_cancel
from app.orchestration.executor import DAGExecutor
from app.orchestration.router import QueryType
from app.state import JobStatus

router = APIRouter(prefix="/api", tags=["chat"])

STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",
}

TERMINAL = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.REJECTED}
ANSWER_KEYS = {"change_vqa": "change_description", "geochat_vqa": "vqa_answer", "geochat_caption": "caption"}


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    messages: list[dict[str, Any]]
    image_ids: list[str]
    scene_set_kind: Literal["single", "bitemporal", "optical_sar"] | None = None
    task: QueryType | None = None
    local_id: str | None = None


def question_of(messages: list[dict[str, Any]]) -> str:
    """Text of the last user message (UIMessage parts of type 'text')."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return " ".join(p.get("text", "") for p in message.get("parts", []) if p.get("type") == "text").strip()
    return ""


def sse(part: dict[str, Any] | str) -> str:
    return f"data: {part if isinstance(part, str) else json.dumps(part, default=str)}\n\n"


def _compact(inputs: dict[str, Any]) -> dict[str, Any]:
    """The step's scalar parameters; bulky arrays stay in the trace."""
    return {k: v for k, v in inputs.items() if isinstance(v, (str, int, float, bool)) or v is None or k == "image_ids"}


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    repo = request.app.state.job_repository
    artifact_repo = request.app.state.artifact_repository
    question = question_of(body.messages)
    job = repo.create()

    updates: queue.Queue = queue.Queue()
    executor = DAGExecutor(
        query_router,
        repo,
        artifact_repo,
        model_mode=request.app.state.settings.model_mode,
        on_trace=lambda t: updates.put(t.model_dump(mode="json")),
    )

    def run() -> None:
        try:
            executor.execute(
                job.id,
                question,
                {"image_ids": body.image_ids},
                scene_set_kind=body.scene_set_kind,
                forced_task=body.task.value if body.task else None,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to the stream, never swallowed
            updates.put({"__error__": str(exc)})
        finally:
            updates.put(None)

    threading.Thread(target=run, daemon=True).start()

    async def stream() -> AsyncIterator[str]:
        meta = {"jobId": job.id, "localId": body.local_id}
        yield sse({"type": "start", "messageMetadata": meta})
        yield sse({"type": "data-job", "data": meta})
        seen: dict[int, str] = {}
        answered = False
        finished_ok = True
        try:
            while True:
                if await request.is_disconnected():
                    request_cancel(job.id)
                    return
                try:
                    item = await asyncio.to_thread(updates.get, True, 0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                if "__error__" in item:
                    finished_ok = False
                    yield sse({"type": "error", "errorText": item["__error__"]})
                    continue

                record = repo.get(job.id)
                trace = item["trace"]
                yield sse({
                    "type": "data-trace",
                    "id": job.id,
                    "data": {
                        "schema_version": item.get("schema_version"),
                        "job_id": job.id,
                        "status": record.status.value,
                        "trace": trace,
                        "failure_reason": record.failure_reason,
                    },
                })

                for i, step in enumerate(trace["steps"]):
                    call_id = f"{job.id}:{i}"
                    state = step["status"]
                    if seen.get(i) is None:
                        yield sse({
                            "type": "tool-input-available",
                            "toolCallId": call_id,
                            "toolName": step["tool_name"],
                            "input": _compact(step["inputs"]),
                            "dynamic": True,
                        })
                        seen[i] = "RUNNING"
                    if state == "SUCCESS" and seen[i] != "SUCCESS":
                        yield sse({"type": "tool-output-available", "toolCallId": call_id, "output": step["outputs"], "dynamic": True})
                        seen[i] = "SUCCESS"
                        key = ANSWER_KEYS.get(step["tool_name"])
                        text = step["outputs"].get(key) if key else None
                        if isinstance(text, str) and text.strip() and not answered:
                            answered = True
                            yield sse({"type": "text-start", "id": f"{job.id}:answer"})
                            yield sse({"type": "text-delta", "id": f"{job.id}:answer", "delta": text})
                            yield sse({"type": "text-end", "id": f"{job.id}:answer"})
                    elif state == "FAILED" and seen[i] != "FAILED":
                        yield sse({"type": "tool-output-error", "toolCallId": call_id, "errorText": step.get("error") or "failed", "dynamic": True})
                        seen[i] = "FAILED"
                        finished_ok = False
        except asyncio.CancelledError:
            # The client aborted (useChat stop()): stop the run before its next step.
            request_cancel(job.id)
            raise

        status = repo.get(job.id).status
        if status not in TERMINAL:
            finished_ok = False
        yield sse({"type": "finish", "finishReason": "stop" if finished_ok and status == JobStatus.COMPLETED else "error"})
        yield sse("[DONE]")

    return StreamingResponse(stream(), media_type="text/event-stream", headers=STREAM_HEADERS)
