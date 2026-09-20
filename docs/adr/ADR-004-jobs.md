# ADR-004: Asynchronous jobs with polling

## Decision

Represent analysis as FastAPI jobs and poll their status from the UI.

## Context

Raster processing and GPU inference exceed a normal browser request lifecycle.
The MVP does not justify Redis, Celery, Kafka, or a distributed queue.

## Options considered

- In-process async/background jobs with polling
- Celery/RQ with Redis
- Synchronous request/response execution

## Chosen approach and trade-offs

The state machine makes failures observable while keeping deployment simple.
Long-running work will be introduced only after ingestion/model phases exist.

## Future migration path

The status API and state machine can be backed by a queue without changing the
frontend polling contract.
