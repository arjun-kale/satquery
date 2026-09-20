# ADR-005: GeoChat adapter for single-image tasks

## Decision

Use GeoChat behind an adapter for captioning, VQA and grounding in the MVP.

## Context

Generic VLMs are not remote-sensing specialised. GeoChat is an existing
remote-sensing VLM, but it is not team-produced adaptation and is not a raw-band
model.

## Options considered

- GeoChat adapter
- Qwen2.5-VL general-purpose VLM
- Build SatCore before MVP

## Chosen approach and trade-offs

GeoChat makes the workflow demonstrable now. It receives only rendered RGB or
false-colour previews; native multispectral/SAR numbers stay deterministic.
Its checkpoint and upstream licenses must be verified before use claims.

## Future migration path

The adapter contract can be pointed at the team LoRA checkpoint, then later a
native-band SatCore implementation.
