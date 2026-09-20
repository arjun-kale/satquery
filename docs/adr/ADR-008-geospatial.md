# ADR-008: Deterministic geospatial toolchain

## Decision

Use Rasterio/GDAL, NumPy/SciPy, PyProj and Shapely for raster, SAR and geodesy.

## Context

Coordinates, indices, calibration and area must be reproducible and must not be
invented by a language model.

## Options considered

- Standard Python geospatial stack
- Browser-only raster arithmetic
- Let a VLM infer measurements

## Chosen approach and trade-offs

The selected libraries are mature and open source. They add native dependencies,
but provide correct CRS and affine-transform handling.

## Future migration path

The tool interfaces can be run in a worker process when inputs become larger.
