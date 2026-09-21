"""Geodesy utilities — pixel ↔ WGS-84, areas, bounding boxes."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pyproj import Transformer
from rasterio.transform import AffineTransformer
from rasterio.crs import CRS
from shapely.geometry import Polygon
from shapely.ops import transform as shapely_transform


def pixel_to_wgs84(
    row: int, col: int, affine_transform, crs: CRS
) -> tuple[float, float]:
    """Convert pixel (row, col) to (latitude, longitude) in WGS-84."""
    transformer = AffineTransformer(affine_transform)
    x, y = transformer.xy(row, col)
    proj = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon, lat = proj.transform(x, y)
    return round(lat, 8), round(lon, 8)


def bounding_box_wgs84(
    affine_transform, width: int, height: int, crs: CRS
) -> list[float]:
    """Return [west, south, east, north] in WGS-84 from raster dimensions."""
    from rasterio.warp import transform_bounds
    from rasterio.transform import array_bounds

    bounds = array_bounds(height, width, affine_transform)
    west, south, east, north = transform_bounds(crs, "EPSG:4326", *bounds)
    return [round(v, 8) for v in [west, south, east, north]]


def polygon_area_m2(geometry: Polygon, crs: CRS) -> float:
    """Return the area of a Shapely polygon in square metres."""
    if crs.is_geographic:
        utm_crs = crs.utm_crs_from_geographic()
        proj = Transformer.from_crs(crs, utm_crs, always_xy=True)
        geometry = shapely_transform(proj.transform, geometry)
    return float(geometry.area)


def change_area_m2(mask: NDArray, affine_transform, crs: CRS) -> float:
    """Return the area (m²) of pixels where *mask* is True/non-zero."""
    pixel_count = int(np.count_nonzero(mask))
    pixel_width = abs(affine_transform.a)
    pixel_height = abs(affine_transform.e)
    pixel_area_native = pixel_width * pixel_height

    if crs.is_geographic:
        # Convert degrees² to m² — use centroid latitude for accuracy
        rows, cols = np.where(mask)
        if rows.size:
            centre_row = int(np.median(rows))
            centre_col = int(np.median(cols))
            lat, _ = pixel_to_wgs84(centre_row, centre_col, affine_transform, crs)
        else:
            lat = 0.0
        import math
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
        pixel_area_native = (pixel_width * m_per_deg_lon) * (pixel_height * m_per_deg_lat)

    return round(pixel_count * pixel_area_native, 2)
