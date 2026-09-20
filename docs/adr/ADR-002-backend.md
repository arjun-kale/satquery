# ADR-002: FastAPI backend

## Decision

Use FastAPI and Pydantic on Python 3.11+ for the backend.

## Context

Rasterio, GDAL, SAR processing and open remote-sensing models are Python-first.
The project also requires typed, schema-valid execution traces.

## Options considered

- FastAPI + Pydantic
- Django REST Framework
- Node.js-only backend

## Chosen approach and trade-offs

FastAPI aligns with the ML/geospatial ecosystem and produces an OpenAPI contract
without extra work. It is a modular monolith, not a microservice platform.

## Future migration path

Route modules and Pydantic DTOs can remain stable if worker execution is split
out later.
