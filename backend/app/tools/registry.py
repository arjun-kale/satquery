"""Registered tool names — router may only select from this enum."""

from enum import StrEnum


class ToolName(StrEnum):
    RASTER_INGEST = "raster_ingest"
    PREVIEW_RENDER = "preview_render"
    NDVI = "ndvi"
    MNDWI = "mndwi"
    NDBI = "ndbi"
    PIXEL_TO_WGS84 = "pixel_to_wgs84"
    BOUNDING_BOX = "bounding_box"
    POLYGON_AREA = "polygon_area"
    CHANGE_AREA = "change_area"
    SAR_CALIBRATE = "sar_calibrate"
    SAR_DESPECKLE = "sar_despeckle"
    COMPATIBILITY_CHECK = "compatibility_check"
    GUARDRAIL_CHECK = "guardrail_check"
    GEOCHAT_CAPTION = "geochat_caption"
    GEOCHAT_VQA = "geochat_vqa"
    GEOCHAT_GROUND = "geochat_ground"
    CHANGEFORMER = "changeformer"
