# ADR-006: ChangeFormer adapter for bi-temporal evidence

## Decision

Use ChangeFormer behind an adapter for co-registered before/after change masks.

## Context

Bi-temporal change detection is a specialist EO task and should not depend on a
general VLM narrative alone.

## Options considered

- ChangeFormer adapter
- Ask a VLM to describe change directly
- Build a custom Siamese model before MVP

## Chosen approach and trade-offs

ChangeFormer yields visual mask evidence; deterministic geodesy calculates area.
It requires registered inputs and does not prove raw SAR/multispectral learning.

## Future migration path

Swap the adapter for a trained change branch after measured evaluation exists.
