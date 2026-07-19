import os

from .schemas import DetectionPayload
from .text import sanitize_text


class IngestInferenceService:
    def __init__(self) -> None:
        self.model_id = os.getenv(
            "HF_AI_HUMAN_MODEL",
            "XOmar/ai_vs_human_detector_deberta_v3_lora",
        )

    def detect_ai_human(self, text: str) -> DetectionPayload:
        sanitized = sanitize_text(text)
        from ..integrations.hf_detector import get_ai_detector

        detector = get_ai_detector()
        result = detector.detect_ai_human(sanitized)
        if not result:
            return DetectionPayload(
                verdict="Unavailable",
                model=getattr(detector, "_loaded_ai_human_model_id", None) or self.model_id,
                available=False,
            )
        return DetectionPayload(
            ai_probability=result.get("ai_probability"),
            human_probability=result.get("human_probability"),
            is_ai=result.get("is_ai"),
            verdict=result.get("verdict") or ("AI" if result.get("is_ai") else "Human"),
            model=getattr(detector, "_loaded_ai_human_model_id", None) or self.model_id,
            available=True,
        )
