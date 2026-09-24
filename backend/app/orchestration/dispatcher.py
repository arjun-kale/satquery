"""DAG node dispatcher — routes tool names to real implementations.

Each tool function receives the current DAG inputs dict and the artifact/job
context, performs its work, writes any output files to the ArtifactRepository,
and returns a plain dict that gets merged back into current_inputs.

MODEL_MODE is read from app settings:
  mock  — deterministic fixture outputs, no GPU required
  local — load model weights from local path (Phase 6)
  modal — call deployed Modal inference function (Phase 5A, after training)
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image

from app.storage.artifacts import ArtifactRepository
from app.ingestion.preview import render_preview
from app.tools.spectral import compute_ndvi, compute_ndwi, compute_mndwi, compute_ndbi
from app.tools.geodesy import bounding_box_wgs84, change_area_m2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_tif_bytes(artifact_repo: ArtifactRepository, image_id: str) -> bytes:
    return artifact_repo.find_upload(image_id).read_bytes()


def _index_to_png(index_array: np.ndarray, colormap: str = "RdYlGn") -> bytes:
    """Convert a float[-1,1] index array to a colourised PNG bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    valid = ~np.isnan(index_array)
    normalised = np.zeros_like(index_array)
    if valid.any():
        lo, hi = np.nanpercentile(index_array, 2), np.nanpercentile(index_array, 98)
        if hi > lo:
            normalised = np.clip((index_array - lo) / (hi - lo), 0, 1)

    cmap = plt.get_cmap(colormap)
    rgba = (cmap(normalised) * 255).astype(np.uint8)
    rgba[~valid, 3] = 0  # transparent nodata

    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mask_to_png(mask: np.ndarray) -> bytes:
    """Convert a boolean change mask to a red-highlight RGBA PNG."""
    h, w = mask.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[mask, 0] = 220  # red channel
    rgba[mask, 3] = 180  # semi-transparent

    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Sentinel-2 / Landsat style band names → role. Band identity must come from the file
# (band descriptions or a "bands" tag); positions alone say nothing about wavelength.
_BAND_ROLES = {
    "blue": {"B02", "B2", "BLUE"},
    "green": {"B03", "B3", "GREEN"},
    "red": {"B04", "B4", "RED"},
    "nir": {"B08", "B8", "B8A", "NIR"},
    "swir": {"B11", "SWIR", "SWIR1", "SWIR16"},
}


def _named_bands(ds) -> dict[str, tuple[int, str]]:
    """Map roles (red, nir, ...) to (1-based band index, declared name)."""
    names = list(ds.descriptions or [])
    tag = ds.tags().get("bands")
    if tag:
        names = [n.strip() for n in tag.split(",")]
    found: dict[str, tuple[int, str]] = {}
    for idx, name in enumerate(names, start=1):
        if not name:
            continue
        for role, aliases in _BAND_ROLES.items():
            if name.upper() in aliases and role not in found:
                found[role] = (idx, name)
    return found


def _choose_index(query: str, bands: dict[str, tuple[int, str]]) -> dict[str, Any]:
    wants_water = any(w in query.lower() for w in ("water", "flood", "reservoir", "lake", "river", "mndwi", "ndwi"))
    declared = ", ".join(sorted(bands)) or "none declared"
    if wants_water:
        if "green" in bands and "swir" in bands:
            return {"fn": compute_mndwi, "bands": ["green", "swir"],
                    "threshold": 0.0, "target": "water"}
        if "green" in bands and "nir" in bands:
            return {"fn": compute_ndwi, "bands": ["green", "nir"],
                    "threshold": 0.0, "target": "water"}
        raise ValueError(
            f"A water index needs green plus NIR or SWIR bands; this scene declares: {declared}."
        )
    if "red" in bands and "nir" in bands:
        return {"fn": compute_ndvi, "bands": ["red", "nir"],
                "threshold": 0.4, "target": "dense vegetation"}
    raise ValueError(f"NDVI needs red and NIR bands; this scene declares: {declared}.")


def _downsample_mask(mask: np.ndarray, max_side: int) -> tuple[np.ndarray, tuple[int, int]]:
    """Block-majority downsample so vectorising stays fast; returns the (x, y) factor."""
    h, w = mask.shape
    fy, fx = max(1, -(-h // max_side)), max(1, -(-w // max_side))
    if fx == 1 and fy == 1:
        return mask, (1, 1)
    hh, ww = (h // fy) * fy, (w // fx) * fx
    blocks = mask[:hh, :ww].reshape(hh // fy, fy, ww // fx, fx)
    return blocks.mean(axis=(1, 3)) >= 0.5, (fx, fy)


def _mask_pixel_area_m2(
    artifact_repo: ArtifactRepository, image_id: str, mask_shape: tuple[int, int]
) -> float | None:
    """Ground area (m²) covered by one pixel of a mask that spans the whole scene.

    Masks are computed on quick-looks, so one mask pixel covers
    (scene width / mask width) × (scene height / mask height) scene pixels.
    """
    try:
        tif = _load_tif_bytes(artifact_repo, image_id)
        with rasterio.MemoryFile(tif) as mem:
            with mem.open() as ds:
                if not (ds.crs and ds.transform):
                    return None
                one_scene_pixel = change_area_m2(np.ones((1, 1), dtype=bool), ds.transform, ds.crs)
                width, height = ds.width, ds.height
    except (FileNotFoundError, rasterio.errors.RasterioIOError):
        return None
    mask_h, mask_w = mask_shape
    return one_scene_pixel * (width / mask_w) * (height / mask_h)


MAX_REGIONS = 9


def mask_to_regions(mask: np.ndarray, pixel_area_m2: float | None) -> list[dict[str, Any]]:
    """Vectorise a binary mask into outline polygons, largest first.

    Coordinates are normalised to [0, 1] of the scene (x right, y down) so they overlay any
    rendering of it. Areas come from pixel counts × pixel ground area, never from a model.
    """
    from rasterio.features import shapes
    from shapely.geometry import shape

    h, w = mask.shape
    polygons = []
    for geom, value in shapes(mask.astype(np.uint8), mask=mask.astype(bool)):
        if value != 1:
            continue
        poly = shape(geom)
        polygons.append((poly.area, poly))
    polygons.sort(key=lambda p: -p[0])

    regions = []
    for index, (pixel_count, poly) in enumerate(polygons[:MAX_REGIONS], start=1):
        simplified = poly.simplify(0.5, preserve_topology=True)
        rings = [simplified.exterior, *simplified.interiors]
        minx, miny, maxx, maxy = poly.bounds
        regions.append({
            "id": index,
            "rings": [[[round(x / w, 5), round(y / h, 5)] for x, y in ring.coords] for ring in rings],
            "bbox": [round(minx / w, 5), round(miny / h, 5), round(maxx / w, 5), round(maxy / h, 5)],
            "pixel_count": int(round(pixel_count)),
            "area_m2": round(pixel_count * pixel_area_m2, 2) if pixel_area_m2 is not None else None,
        })
    return regions


def _get_model_adapter(model_mode: str):
    """Return the appropriate model adapter based on MODEL_MODE."""
    if model_mode == "mock":
        from app.models.mock import MockModelAdapter
        return MockModelAdapter()
    elif model_mode == "modal":
        from app.models.geochat import GeoChatAdapter
        return GeoChatAdapter(mode="modal")
    else:
        from app.models.geochat import GeoChatAdapter
        return GeoChatAdapter(mode="local")


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def dispatch_tool(
    tool_name: str,
    inputs: dict[str, Any],
    artifact_repo: ArtifactRepository,
    job_id: str,
    model_mode: str = "mock",
) -> dict[str, Any]:
    """Dispatch a DAG node to its real implementation."""

    image_ids: list[str] = inputs.get("image_ids", [])
    image_id_a = image_ids[0] if len(image_ids) >= 1 else None
    image_id_b = image_ids[1] if len(image_ids) >= 2 else None

    # ------------------------------------------------------------------
    if tool_name == "preview":
        if not image_id_a:
            raise ValueError("preview: no image_ids in inputs")

        tif = _load_tif_bytes(artifact_repo, image_id_a)
        png_bytes, band_map = render_preview(tif)

        path = artifact_repo.artifact_path(job_id, "preview.png")
        path.write_bytes(png_bytes)

        # Also render preview B for bi-temporal jobs
        if image_id_b:
            tif_b = _load_tif_bytes(artifact_repo, image_id_b)
            png_b, _ = render_preview(tif_b)
            artifact_repo.artifact_path(job_id, "preview_b.png").write_bytes(png_b)

        return {
            "preview_url": f"/api/jobs/{job_id}/artifacts/preview.png",
            "preview_b_url": f"/api/jobs/{job_id}/artifacts/preview_b.png" if image_id_b else None,
            "band_map": band_map,
        }

    # ------------------------------------------------------------------
    elif tool_name == "spectral_index":
        if not image_id_a:
            raise ValueError("spectral_index: no image_ids in inputs")

        tif = _load_tif_bytes(artifact_repo, image_id_a)
        with rasterio.MemoryFile(tif) as mem:
            with mem.open() as ds:
                bands = _named_bands(ds)
                transform, crs = ds.transform, ds.crs
                read = lambda role: ds.read(bands[role][0]).astype(float)  # noqa: E731
                spec = _choose_index(inputs.get("query", ""), bands)
                result = spec["fn"](*(read(b) for b in spec["bands"]))

        index = result["array"]
        artifact_repo.artifact_path(job_id, "index_mask.png").write_bytes(_index_to_png(index))

        # Deterministic threshold rule → outline evidence; the rule is recorded, not hidden.
        target = np.nan_to_num(index, nan=-1.0) > spec["threshold"]
        coarse, factor = _downsample_mask(target, 512)
        one_px = (
            change_area_m2(np.ones((1, 1), dtype=bool), transform, crs) if crs and transform else None
        )
        regions = mask_to_regions(coarse, one_px * factor[0] * factor[1] if one_px else None)
        covered = int(np.count_nonzero(target))

        return {
            "index_type": result["name"],
            "bands_used": {r: f"band {bands[r][0]} ({bands[r][1]})" for r in spec["bands"]},
            "index_mean": round(result["mean"], 4),
            "index_min": round(result["min"], 4),
            "index_max": round(result["max"], 4),
            "rule": f"{result['name']} > {spec['threshold']:g} → {spec['target']}",
            "target": spec["target"],
            "target_pixels": covered,
            "target_fraction": round(covered / target.size, 4),
            "target_area_m2": round(covered * one_px, 2) if one_px else None,
            "index_regions": regions,
            "mask_url": f"/api/jobs/{job_id}/artifacts/index_mask.png",
        }

    # ------------------------------------------------------------------
    elif tool_name == "geochat_vqa":
        adapter = _get_model_adapter(model_mode)
        query = inputs.get("query", "Describe what you see in this satellite image.")
        band_map = inputs.get("band_map", "B1/B2/B3")

        preview_path = artifact_repo.artifact_path(job_id, "preview.png")
        png_bytes = preview_path.read_bytes() if preview_path.exists() else b""

        result = adapter.answer(png_bytes, query, band_map=band_map)
        return {
            "vqa_answer": result.text,
            "confidence": result.confidence,
            "confidence_source": result.confidence_source,
            "model_mode": result.model_mode,
            "weights": result.weights,
        }

    # ------------------------------------------------------------------
    elif tool_name == "geochat_caption":
        adapter = _get_model_adapter(model_mode)
        band_map = inputs.get("band_map", "B1/B2/B3")

        preview_path = artifact_repo.artifact_path(job_id, "preview.png")
        png_bytes = preview_path.read_bytes() if preview_path.exists() else b""

        result = adapter.caption(png_bytes, band_map=band_map)
        return {
            "caption": result.text,
            "confidence": result.confidence,
            "confidence_source": result.confidence_source,
            "model_mode": result.model_mode,
            "weights": result.weights,
        }

    # ------------------------------------------------------------------
    elif tool_name == "geochat_grounding":
        adapter = _get_model_adapter(model_mode)
        query = inputs.get("query", "Highlight the main object")
        band_map = inputs.get("band_map", "B1/B2/B3")

        preview_path = artifact_repo.artifact_path(job_id, "preview.png")
        png_bytes = preview_path.read_bytes() if preview_path.exists() else b""

        boxes = adapter.ground(png_bytes, query, band_map=band_map)
        box_list = [
            {
                "label": b.label,
                "confidence": b.confidence,
                "x_min": b.x_min,
                "y_min": b.y_min,
                "x_max": b.x_max,
                "y_max": b.y_max,
            }
            for b in boxes
        ]

        # Persist boxes for frontend to read
        boxes_path = artifact_repo.artifact_path(job_id, "grounding_boxes.json")
        boxes_path.write_text(json.dumps(box_list))

        return {
            "weights": getattr(adapter, "last_weights", None),
            "grounding_boxes": box_list,
            "boxes_url": f"/api/jobs/{job_id}/artifacts/grounding_boxes.json",
        }

    # ------------------------------------------------------------------
    elif tool_name == "geodesy":
        if not image_id_a:
            return {"area_m2": None, "bounds_wgs84": None}

        tif = _load_tif_bytes(artifact_repo, image_id_a)
        with rasterio.MemoryFile(tif) as mem:
            with mem.open() as ds:
                crs = ds.crs
                transform = ds.transform
                width, height = ds.width, ds.height

        if crs and transform:
            bounds = bounding_box_wgs84(transform, width, height, crs)
            pixel_area = abs(transform.a * transform.e)
            total_area = round(pixel_area * width * height, 2)
        else:
            bounds = None
            total_area = None

        return {
            "bounds_wgs84": bounds,
            "area_m2": total_area,
            "width_px": width,
            "height_px": height,
        }

    # ------------------------------------------------------------------
    elif tool_name == "changeformer":
        if not image_id_b:
            raise ValueError("changeformer: requires two image_ids for bi-temporal analysis")

        if model_mode == "mock":
            from app.models.mock import MockModelAdapter
            adapter = MockModelAdapter()
        else:
            from app.models.changeformer import ChangeFormerAdapter
            adapter = ChangeFormerAdapter(mode=model_mode)
        band_map = inputs.get("band_map", "B1/B2/B3")

        preview_a = artifact_repo.artifact_path(job_id, "preview.png")
        preview_b = artifact_repo.artifact_path(job_id, "preview_b.png")

        if not preview_a.exists() or not preview_b.exists():
            raise RuntimeError("changeformer: preview PNGs not found — run 'preview' node first")

        png_a = preview_a.read_bytes()
        png_b = preview_b.read_bytes()

        change_mask = adapter.detect_change(
            png_a, png_b, band_map=band_map
        )

        mask_png = _mask_to_png(change_mask.mask)
        mask_path = artifact_repo.artifact_path(job_id, "change_mask.png")
        mask_path.write_bytes(mask_png)

        # Persist raw mask as numpy for change_area node
        np.save(str(artifact_repo.artifact_path(job_id, "change_mask.npy")), change_mask.mask)

        pixel_area_m2 = None
        if image_id_a:
            pixel_area_m2 = _mask_pixel_area_m2(artifact_repo, image_id_a, change_mask.mask.shape)
        regions = mask_to_regions(change_mask.mask, pixel_area_m2)
        artifact_repo.artifact_path(job_id, "change_regions.json").write_text(json.dumps(regions))

        return {
            "change_regions": regions,
            "confidence_source": change_mask.confidence_source,
            "model_mode": "mock" if model_mode == "mock" else adapter.model_mode,
            "changed_pixels": int(np.count_nonzero(change_mask.mask)),
            "total_pixels": int(change_mask.mask.size),
            "change_ratio": round(float(np.count_nonzero(change_mask.mask)) / change_mask.mask.size, 4),
            "changed_area_m2": change_mask.changed_area_m2,
            "confidence": change_mask.confidence,
            "change_mask_url": f"/api/jobs/{job_id}/artifacts/change_mask.png",
        }

    # ------------------------------------------------------------------
    elif tool_name == "change_area":
        npy_path = artifact_repo.artifact_path(job_id, "change_mask.npy")
        if not npy_path.exists():
            return {"change_area_m2": None, "message": "No change mask available"}

        mask = np.load(str(npy_path))

        # Try to get affine + CRS from image A
        area_m2 = None
        pixel_area_m2 = None
        if image_id_a:
            pixel_area_m2 = _mask_pixel_area_m2(artifact_repo, image_id_a, mask.shape)
            if pixel_area_m2 is not None:
                area_m2 = round(int(np.count_nonzero(mask)) * pixel_area_m2, 2)

        return {
            "change_area_m2": area_m2,
            "changed_pixels": int(np.count_nonzero(mask)),
            "mask_pixel_area_m2": pixel_area_m2,
            "area_method": "changed mask pixels × ground area of one mask pixel (from the GeoTIFF transform)",
        }

    # ------------------------------------------------------------------
    elif tool_name == "change_vqa":
        """Answer a natural language question about what changed."""
        adapter = _get_model_adapter(model_mode)
        band_map = inputs.get("band_map", "B1/B2/B3")
        query = inputs.get("query", "What changed between these two satellite images? Describe the type, location, and extent of change.")

        preview_a = artifact_repo.artifact_path(job_id, "preview.png")
        png_bytes = preview_a.read_bytes() if preview_a.exists() else b""

        result = adapter.answer(png_bytes, query, band_map=band_map)

        change_ratio = inputs.get("change_ratio", 0)
        change_area = inputs.get("change_area_m2")

        # Numbers come from the mask, never from the language model; keep them separate so
        # the UI can label which sentences are measured and which are model text.
        measured = []
        if change_area:
            measured.append(f"Estimated changed area: {change_area:,.0f} m².")
        if change_ratio:
            measured.append(f"Change ratio: {change_ratio * 100:.1f}% of scene.")

        return {
            "change_description": result.text,
            "measured_summary": " ".join(measured) or None,
            "vlm_input": "T1 quick-look only (the VLM takes one image)",
            "confidence": result.confidence,
            "confidence_source": result.confidence_source,
            "model_mode": result.model_mode,
            "weights": result.weights,
        }

    # ------------------------------------------------------------------
    elif tool_name == "cross_modal_fusion":
        from app.tools.fusion import cross_modal_fusion
        preview_a = artifact_repo.artifact_path(job_id, "preview.png")
        preview_b = artifact_repo.artifact_path(job_id, "preview_b.png")
        if not preview_a.exists() or not preview_b.exists():
            raise RuntimeError("cross_modal_fusion requires both preview.png and preview_b.png")
        
        fused_png, analysis = cross_modal_fusion(preview_a.read_bytes(), preview_b.read_bytes())
        
        fused_path = artifact_repo.artifact_path(job_id, "fused_preview.png")
        fused_path.write_bytes(fused_png)
        
        return {
            "fusion_method": analysis["fusion_method"],
            "fusion_description": analysis["description"],
            "fused_preview_url": f"/api/jobs/{job_id}/artifacts/fused_preview.png",
        }

    # ------------------------------------------------------------------
    elif tool_name in ("sar_calibrate", "sar_despeckle"):
        # app.tools.sar implements these, but calibration constants must come from product
        # metadata the ingest path doesn't carry yet — so nothing is computed here, and the
        # trace says so instead of reporting invented parameters.
        return {
            "simulated": True,
            "note": f"{tool_name} is not wired to product calibration metadata yet; no computation ran.",
        }

    elif tool_name == "compatibility":
        if not (image_id_a and image_id_b):
            raise ValueError("compatibility: requires two image_ids")
        from app.ingestion.compatibility import check_compatibility
        report = check_compatibility(
            _load_tif_bytes(artifact_repo, image_id_a), _load_tif_bytes(artifact_repo, image_id_b)
        )
        if not report.compatible:
            raise ValueError(report.rejection_reason)
        return {"compatible": True}

    elif tool_name in ("geochat_summary", "mndwi"):
        return {"simulated": True, "note": f"{tool_name} is a placeholder step; no computation ran."}


    # ------------------------------------------------------------------
    else:
        raise ValueError(f"Unknown tool: {tool_name!r}")
