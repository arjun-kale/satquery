import io
from PIL import Image, ImageChops
import numpy as np

def cross_modal_fusion(optical_png: bytes, sar_png: bytes) -> tuple[bytes, dict]:
    """Fuse optical and SAR previews into a false-color composite."""
    opt_img = Image.open(io.BytesIO(optical_png)).convert("RGBA")
    sar_img = Image.open(io.BytesIO(sar_png)).convert("RGBA")
    
    # Simple fusion: use SAR as a luminosity layer or add as red channel
    # Convert SAR to grayscale for intensity
    sar_gray = sar_img.convert("L")
    
    # Create a red tint from SAR
    sar_red = Image.new("RGBA", opt_img.size, (255, 0, 0, 0))
    sar_red.putalpha(sar_gray)
    
    # Blend
    fused_img = Image.alpha_composite(opt_img, sar_red)
    
    buf = io.BytesIO()
    fused_img.save(buf, format="PNG")
    
    analysis = {
        "fusion_method": "sar_red_overlay",
        "description": "SAR intensity overlaid on optical preview as red channel to highlight structural features."
    }
    
    return buf.getvalue(), analysis
