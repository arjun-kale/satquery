"""Fetch the empty-state sample scene sets: real, openly licensed Copernicus scenes.

    cd backend && .venv/bin/python scripts/fetch_samples.py

Writes small windowed crops (no full tiles) plus ``manifest.json`` to ``<data_dir>/samples``.
Sentinel-2 L2A comes from Element 84 Earth Search (public COGs on AWS); Sentinel-1 RTC comes
from Microsoft Planetary Computer (anonymous SAS token). Copernicus Sentinel data are free and
open; attribution: "Contains modified Copernicus Sentinel data [year]".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform as warp_transform
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings  # noqa: E402

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-1-rtc"

S2_BANDS = [("red", "B04"), ("green", "B03"), ("blue", "B02"), ("nir", "B08"), ("swir16", "B11")]
SIZE_PX = 1024  # 10.24 km at 10 m
S2_LICENSE = "Copernicus Sentinel data, free and open (attribution required)"


def s2_item(item_id: str) -> dict:
    r = httpx.get(f"{EARTH_SEARCH}/collections/sentinel-2-l2a/items/{item_id}", timeout=60)
    r.raise_for_status()
    return r.json()


def s2_latest_clear(lon: float, lat: float, start: str, end: str) -> dict:
    body = {
        "collections": ["sentinel-2-l2a"],
        "intersects": {"type": "Point", "coordinates": [lon, lat]},
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": 2}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        "limit": 1,
    }
    r = httpx.post(f"{EARTH_SEARCH}/search", json=body, timeout=60)
    r.raise_for_status()
    return r.json()["features"][0]


def grid_for(item: dict, lon: float, lat: float) -> tuple[rasterio.crs.CRS, rasterio.Affine]:
    """A SIZE_PX square 10 m grid centred on (lon, lat) in the item's UTM zone."""
    with rasterio.open(item["assets"]["red"]["href"]) as ds:
        crs = ds.crs
        xs, ys = warp_transform("EPSG:4326", crs, [lon], [lat])
        # Snap to the 10 m pixel grid so every band and date aligns exactly.
        x0 = round((xs[0] - SIZE_PX * 5) / 10) * 10
        y0 = round((ys[0] + SIZE_PX * 5) / 10) * 10
    return crs, rasterio.Affine(10, 0, x0, 0, -10, y0)


def read_on_grid(href: str, crs, transform, resampling=Resampling.bilinear) -> np.ndarray:
    with rasterio.open(href) as src:
        with WarpedVRT(src, crs=crs, transform=transform, width=SIZE_PX, height=SIZE_PX,
                       resampling=resampling) as vrt:
            return vrt.read(1)


def write_s2(item: dict, crs, transform, out: Path) -> None:
    arrays = [read_on_grid(item["assets"][key]["href"], crs, transform) for key, _ in S2_BANDS]
    date = item["properties"]["datetime"][:10]
    with rasterio.open(out, "w", driver="GTiff", width=SIZE_PX, height=SIZE_PX, count=len(arrays),
                       dtype="uint16", crs=crs, transform=transform, compress="deflate") as dst:
        for i, (arr, (_, name)) in enumerate(zip(arrays, S2_BANDS), start=1):
            dst.write(arr.astype("uint16"), i)
            dst.set_band_description(i, name)
        dst.update_tags(
            modality="optical", sensor="Sentinel-2 MSI (L2A)", acquired_at=date,
            bands=",".join(n for _, n in S2_BANDS),
            source=f"Earth Search sentinel-2-l2a / {item['id']}", license=S2_LICENSE,
        )
    print(f"  wrote {out.name} ({date})")


def write_s1(lon: float, lat: float, near_date: str, crs, transform, out: Path) -> None:
    token = httpx.get(PC_TOKEN, timeout=30).json()["token"]
    body = {
        "collections": ["sentinel-1-rtc"],
        "intersects": {"type": "Point", "coordinates": [lon, lat]},
        "datetime": f"{near_date}T00:00:00Z/{near_date[:8]}28T23:59:59Z",
        "limit": 1,
    }
    r = httpx.post(f"{PC_STAC}/search", json=body, timeout=60)
    r.raise_for_status()
    item = r.json()["features"][0]
    vv = read_on_grid(f"{item['assets']['vv']['href']}?{token}", crs, transform)
    vh = read_on_grid(f"{item['assets']['vh']['href']}?{token}", crs, transform)
    date = item["properties"]["datetime"][:10]
    with rasterio.open(out, "w", driver="GTiff", width=SIZE_PX, height=SIZE_PX, count=2,
                       dtype="float32", crs=crs, transform=transform, compress="deflate",
                       nodata=0) as dst:
        dst.write(vv.astype("float32"), 1)
        dst.write(vh.astype("float32"), 2)
        dst.set_band_description(1, "VV")
        dst.set_band_description(2, "VH")
        dst.update_tags(
            modality="sar", sensor="Sentinel-1 C-SAR (RTC, gamma0 linear)", acquired_at=date,
            polarisation="VV,VH", bands="VV,VH",
            source=f"Planetary Computer sentinel-1-rtc / {item['id']}", license=S2_LICENSE,
        )
    print(f"  wrote {out.name} ({date})")


def main() -> None:
    out_dir = Settings().data_dir / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Krishna Raja Sagara reservoir, Karnataka: low before the monsoon, full after it.
    krs = (76.52, 12.43)
    print("Reservoir, two dates (Sentinel-2)")
    t1, t2 = s2_item("S2B_43PFP_20240505_0_L2A"), s2_item("S2A_43PFP_20241216_0_L2A")
    crs, transform = grid_for(t1, *krs)
    write_s2(t1, crs, transform, out_dir / "krs_2024-05-05_s2.tif")
    write_s2(t2, crs, transform, out_dir / "krs_2024-12-16_s2.tif")

    print("Reservoir, optical + SAR (Sentinel-1 RTC)")
    write_s1(*krs, "2024-12-10", crs, transform, out_dir / "krs_2024-12_s1.tif")

    # Bengaluru city centre.
    blr = (77.59, 12.975)
    print("City, single image (Sentinel-2)")
    city = s2_latest_clear(*blr, "2024-01-01", "2024-03-31")
    crs_c, transform_c = grid_for(city, *blr)
    write_s2(city, crs_c, transform_c, out_dir / "bengaluru_s2.tif")

    manifest = {"samples": [
        {
            "id": "reservoir-two-dates", "title": "Reservoir — two dates", "kind": "bitemporal",
            "description": "Krishna Raja Sagara reservoir, Karnataka, before (May) and after (Dec) the 2024 monsoon.",
            "suggested_question": "What changed between these dates, and where?",
            "source": "Sentinel-2 L2A via Element 84 Earth Search", "license": S2_LICENSE,
            "files": [{"role": "T1", "path": "krs_2024-05-05_s2.tif"}, {"role": "T2", "path": "krs_2024-12-16_s2.tif"}],
        },
        {
            "id": "city-single", "title": "City — single image", "kind": "single",
            "description": "Bengaluru city centre, Sentinel-2 true colour plus NIR and SWIR.",
            "suggested_question": "Describe this scene",
            "source": "Sentinel-2 L2A via Element 84 Earth Search", "license": S2_LICENSE,
            "files": [{"role": "image", "path": "bengaluru_s2.tif"}],
        },
        {
            "id": "reservoir-optical-sar", "title": "Reservoir — optical + SAR", "kind": "optical_sar",
            "description": "Krishna Raja Sagara reservoir: Sentinel-2 (16 Dec 2024) with Sentinel-1 RTC from December 2024.",
            "suggested_question": "Use optical and SAR together to show the water",
            "source": "Sentinel-2 L2A (Earth Search) + Sentinel-1 RTC (Planetary Computer)", "license": S2_LICENSE,
            "files": [{"role": "optical", "path": "krs_2024-12-16_s2.tif"}, {"role": "sar", "path": "krs_2024-12_s1.tif"}],
        },
    ]}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"manifest → {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
