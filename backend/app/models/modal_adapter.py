"""Adapter for querying the deployed Modal inference worker."""
import modal
from app.models.base import VLMAdapter, ModelResult, GroundingBox

class ModalModelAdapter(VLMAdapter):
    """Adapter that calls the satquery-m1-infer Modal application."""
    
    def __init__(self):
        try:
            self.infer_func = modal.Cls.lookup("satquery-m1-infer", "GeoChatInfer")
        except Exception as e:
            raise RuntimeError(f"Could not connect to Modal satquery-m1-infer app: {e}")

    def answer(self, image_bytes: bytes, query: str, **kwargs) -> ModelResult:
        self.assert_preview_input(image_bytes)
        result = self.infer_func.answer.remote(image_bytes, query)
        return ModelResult(
            text=result["text"],
            confidence=result.confidence if hasattr(result, "confidence") else result.get("confidence", 0.95),
            model_mode=result.model_mode if hasattr(result, "model_mode") else result.get("model_mode", "modal")
        )

    def caption(self, image_bytes: bytes, **kwargs) -> ModelResult:
        self.assert_preview_input(image_bytes)
        result = self.infer_func.caption.remote(image_bytes)
        return ModelResult(
            text=result["text"],
            confidence=result.confidence if hasattr(result, "confidence") else result.get("confidence", 0.90),
            model_mode=result.model_mode if hasattr(result, "model_mode") else result.get("model_mode", "modal")
        )

    def ground(self, image_bytes: bytes, query: str, **kwargs) -> list[GroundingBox]:
        self.assert_preview_input(image_bytes)
        result = self.infer_func.ground.remote(image_bytes, query)
        boxes_data = result.get("boxes", [])
        boxes = []
        for b in boxes_data:
            boxes.append(GroundingBox(
                label=b["label"],
                confidence=b["confidence"],
                x_min=b["x_min"],
                y_min=b["y_min"],
                x_max=b["x_max"],
                y_max=b["y_max"]
            ))
        return boxes
