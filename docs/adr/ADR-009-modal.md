# ADR-009: Modal as optional GPU worker

## Decision

Use Modal only for short free-credit M1 training and optional inference jobs.

## Context

The project has zero budget and no local GPU guarantee. It must still work in
mock/local mode when credit, a payment method, or a GPU allocation is absent.

## Options considered

- Optional Modal worker
- Always-on hosted GPU backend
- Block development until local GPU access exists

## Chosen approach and trade-offs

Modal can make short experiments feasible but is not the stateful backend and
does not support a sovereign deployment claim.

## Future migration path

Replace the adapter endpoint with on-premise/India-hosted inference for a final
deployment.
