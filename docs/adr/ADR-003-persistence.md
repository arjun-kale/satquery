# ADR-003: SQLite and filesystem persistence

## Decision

Use SQLite for job metadata and the local filesystem for uploads/artifacts.

## Context

The MVP has one operator and no paid infrastructure budget. It must also run on
a judge laptop with no database service.

## Options considered

- SQLite + filesystem
- PostgreSQL in Docker
- Modal Volume-backed state

## Chosen approach and trade-offs

SQLite avoids service setup and is adequate for one local FastAPI process.
Modal is never the stateful backend because its ephemeral containers would make
SQLite/filesystem state unreliable.

## Future migration path

The `storage/` repository boundary can move to Postgres/object storage when
concurrency or remote persistence becomes necessary.
