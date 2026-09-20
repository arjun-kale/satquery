# ADR-010: Vercel is UI-only

## Decision

Vercel serves the Next.js UI only. Browsers upload raster data directly to
FastAPI; Vercel Functions never relay file bytes or host models.

## Context

PyTorch/GDAL/model-weight workloads do not fit a frontend function environment,
and routing large imagery through it widens the sensitive-data boundary.

## Options considered

- UI-only Vercel deployment
- Vercel Functions as Python/model backend
- Entirely local Next.js frontend

## Chosen approach and trade-offs

The UI remains cheap and simple while FastAPI owns data handling. Vercel is used
only with public sample imagery in remote-prototype mode.

## Future migration path

Deploy the UI locally or to approved Indian infrastructure for sovereignty.
