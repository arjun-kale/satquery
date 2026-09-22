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
from app.tools.spectral import compute_ndvi, compute_mndwi, compute_ndbi
from app.tools.geodesy import bounding_box_wgs84, change_area_m2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_tif_bytes(artifact_repo: ArtifactRepository, image_id: str) -> bytes:
    path = artifact_repo.upload_path(image_id)
    if not path.exists():
        raise FileNotFoundError(f"Uploaded file not found: {path}")
    return path.read_bytes()


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
                band_count = ds.count
                # Use first 3 bands as R/G/B proxy; adapt for real Sentinel-2 later
                b1 = ds.read(1).astype(float)
                b2 = ds.read(min(2, band_count)).astype(float)
                b3 = ds.read(min(3, band_count)).astype(float)

        # Compute MNDWI as default (green / SWIR proxy with available bands)
        result = compute_mndwi(b2, b3)  # band2=green proxy, band3=SWIR proxy
        index_name = result["name"]

        mask_png = _index_to_png(result["array"])
        mask_path = artifact_repo.artifact_path(job_id, "index_mask.png")
        mask_path.write_bytes(mask_png)

        return {
            "index_type": index_name,
            "index_mean": round(result["mean"], 4),
            "index_min": round(result["min"], 4),
            "index_max": round(result["max"], 4),
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
            "model_mode": result.model_mode,
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
            "model_mode": result.model_mode,
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

        from app.models.changeformer import ChangeFormerAdapter
        adapter = ChangeFormerAdapter()
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

        return {
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
        if image_id_a:
            try:
                tif = _load_tif_bytes(artifact_repo, image_id_a)
                with rasterio.MemoryFile(tif) as mem:
                    with mem.open() as ds:
                        if ds.crs and ds.transform:
                            area_m2 = change_area_m2(mask, ds.transform, ds.crs)
            except Exception:
                pass

        return {
            "change_area_m2": area_m2,
            "changed_pixels": int(np.count_nonzero(mask)),
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

        summary = result.text
        if change_area:
            summary += f" Estimated changed area: {change_area:,.0f} m²."
        if change_ratio:
            summary += f" Change ratio: {change_ratio * 100:.1f}% of scene."

        return {
            "change_description": summary,
            "confidence": result.confidence,
            "model_mode": result.model_mode,
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
    elif tool_name == "sar_calibrate":
        # Simulate SAR calibration by returning the preview as calibrated SAR for the MVP pipeline
        return {"status": "ok", "calibration_factor": 1.0, "incidence_angle": 30.0}

    elif tool_name == "sar_despeckle":
        # Simulate despeckling
        return {"status": "ok", "window_size": 5, "noise_var": 0.05}

    elif tool_name == "cross_modal_fusion":
        from app.tools.fusion import cross_modal_fusion
        preview_a = artifact_repo.artifact_path(job_id, "preview.png")
        preview_b = artifact_repo.artifact_path(job_id, "preview_b.png")
        if not preview_a.exists() or not preview_b.exists():
            raise RuntimeError("cross_modal_fusion requires both preview.png and preview_b.png")

        png_a = preview_a.read_bytes()
        png_b = preview_b.read_bytes()

        fused_png, analysis = cross_modal_fusion(png_a, png_b)
        fusion_path = artifact_repo.artifact_path(job_id, "fused_preview.png")
        fusion_path.write_bytes(fused_png)

        # Overwrite preview.png so geochat_vqa uses the fused image!
        # This is a cool trick to let the single-image VLM answer queries about the fused result.
        preview_a.write_bytes(fused_png)

        return {
            "fusion_method": analysis["fusion_method"],
            "fusion_description": analysis["description"],
            "fused_url": f"/api/jobs/{job_id}/artifacts/fused_preview.png"
        }

    elif tool_name in ("compatibility", "geochat_summary", "mndwi"):
        return {"status": "ok", "tool": tool_name}

    # ------------------------------------------------------------------
    else:
        raise ValueError(f"Unknown tool: {tool_name!r}")
