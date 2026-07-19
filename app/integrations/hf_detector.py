from __future__ import annotations

import logging
import os
import threading
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple, Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from peft import PeftModel, PeftConfig

# Keep your project config import
try:
    from ..config import get_settings
except ImportError:
    # Fallback for standalone testing
    def get_settings(): return None

logger = logging.getLogger(__name__)

class AIDetector:
    """
    Dual-model detector for AI-generated content:
    1. AI vs Human detection using DeBERTa v3 LoRA (ShoaibSSM/ai_vs_human_detector_deberta_v3_lora)
    2. Model Family detection for AI-generated text (XOmar/model_family_detector_deberta_v3_balanced)
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._ai_human_model = None
        self._ai_human_tokenizer = None
        self._family_model = None
        self._family_tokenizer = None
        # Torch modules are shared by all requests in this process. Serialising
        # forward passes prevents concurrent single and batch requests from
        # racing over the same GPU context.
        self._inference_lock = threading.RLock()

        # Allow overriding the adapter checkpoint via env for flexibility
        self._ai_human_adapter_id = os.getenv(
            "HF_AI_HUMAN_MODEL",
            "ShoaibSSM/ai_vs_human_detector_deberta_v3_lora/checkpoint-68090",
        )
        
        # Skip model loading if disabled (e.g., in Docker blockchain nodes)
        if os.getenv("DISABLE_AI_MODELS", "false").lower() == "true":
            logger.warning("⚠️  AI model loading disabled via DISABLE_AI_MODELS env var")
            self._device = "cpu"
            return
        
        # Determine device automatically
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🚀 Initializing AI Detector on device: {self._device.upper()}")
        
        self._load_models()

    def _load_models(self) -> None:
        """Load both AI detection models. If the family model fails, keep AI/Human alive."""
        # --- 1. Load AI vs Human Detector (LoRA) ---
        try:
            logger.info(
                "⏳ Loading AI vs Human detector (LoRA): %s",
                self._ai_human_adapter_id,
            )

            # Handle subfolder checkpoints explicitly (e.g., repo/checkpoint-12345)
            adapter_id = self._ai_human_adapter_id
            repo_id = adapter_id
            subfolder = None
            if "/checkpoint" in adapter_id:
                repo_id, suffix = adapter_id.split("/checkpoint", 1)
                subfolder = f"checkpoint{suffix}"

            # Some checkpoints store adapter files one level up; try subfolder-first, then parent
            try:
                config = PeftConfig.from_pretrained(repo_id, subfolder=subfolder)
            except Exception as exc:
                logger.warning(
                    "Adapter config not found at %s (subfolder=%s, %s). Trying parent repo...",
                    repo_id,
                    subfolder,
                    exc,
                )
                config = PeftConfig.from_pretrained(repo_id)
                subfolder = None

            # Load Base Model
            base_model = AutoModelForSequenceClassification.from_pretrained(
                config.base_model_name_or_path,
                num_labels=2,  # Binary classification head
            )

            # Load LoRA Adapter
            self._ai_human_model = PeftModel.from_pretrained(
                base_model, repo_id, subfolder=subfolder
            )
            self._ai_human_model.to(self._device)
            self._ai_human_model.eval()

            # Smart Tokenizer Loading (Fallback to base if adapter has no tokenizer)
            try:
                self._ai_human_tokenizer = AutoTokenizer.from_pretrained(
                    repo_id, subfolder=subfolder
                )
            except Exception:
                logger.warning(
                    "Tokenizer not found in adapter, loading from base model..."
                )
                self._ai_human_tokenizer = AutoTokenizer.from_pretrained(
                    config.base_model_name_or_path
                )

            logger.info("✅ AI vs Human detector loaded.")

        except Exception as exc:
            logger.error(f"❌ Failed to load AI/Human detector: {exc}")
            self._ai_human_model = None
            self._ai_human_tokenizer = None
            return

        # --- 2. Load Model Family Detector (optional) ---
        try:
            logger.info("⏳ Loading Model Family detector (Balanced)...")
            family_model_id = "XOmar/model_family_detector_deberta_v3_balanced"

            self._family_model = AutoModelForSequenceClassification.from_pretrained(
                family_model_id
            )
            self._family_model.to(self._device)
            self._family_model.eval()

            self._family_tokenizer = AutoTokenizer.from_pretrained(family_model_id)

            logger.info("✅ Model Family detector loaded.")

        except Exception as exc:
            logger.warning(
                "⚠️ Model Family detector unavailable; continuing with AI/Human only: %s",
                exc,
            )
            self._family_model = None
            self._family_tokenizer = None

    @property
    def available(self) -> bool:
        """Check if models are loaded and ready."""
        return self._ai_human_model is not None and self._ai_human_tokenizer is not None

    def detect_ai_human(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detect if text is AI-generated or human-written.
        """
        return self.detect_ai_human_batch([text], batch_size=1)[0]

    def detect_ai_human_batch(
        self, texts: Sequence[str], *, batch_size: int = 16
    ) -> List[Optional[Dict[str, Any]]]:
        """Run vectorized AI/human inference while bounding model memory use."""
        results: List[Optional[Dict[str, Any]]] = [None] * len(texts)
        if not self.available:
            return results

        batch_size = max(1, int(batch_size))
        try:
            with self._inference_lock:
                for start in range(0, len(texts), batch_size):
                    chunk = list(texts[start : start + batch_size])
                    non_empty = [(idx, text) for idx, text in enumerate(chunk) if text.strip()]
                    if not non_empty:
                        continue
                    inputs = self._ai_human_tokenizer(
                        [text for _, text in non_empty],
                        return_tensors="pt",
                        truncation=True,
                        max_length=512,
                        padding=True,
                    ).to(self._device)
                    with torch.no_grad():
                        outputs = self._ai_human_model(**inputs)
                        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)

                    id2label = self._ai_human_model.config.id2label
                    ai_index = 1
                    for idx, label in id2label.items():
                        if "AI" in str(label).upper() or "LABEL_1" in str(label).upper():
                            ai_index = int(idx)
                            break
                    human_index = 1 - ai_index

                    for row, (chunk_index, _) in enumerate(non_empty):
                        ai_prob = float(probabilities[row][ai_index].item())
                        human_prob = float(probabilities[row][human_index].item())
                        results[start + chunk_index] = {
                            "ai_probability": ai_prob,
                            "human_probability": human_prob,
                            "is_ai": ai_prob > 0.5,
                            "verdict": "AI" if ai_prob > 0.5 else "Human",
                        }
        except Exception as exc:
            logger.error("Batched AI/Human detection failed: %s", exc)
        return results

    def detect_model_family(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detect which AI model family generated the text.
        """
        return self.detect_model_family_batch([text], batch_size=1)[0]

    def detect_model_family_batch(
        self, texts: Sequence[str], *, batch_size: int = 16
    ) -> List[Optional[Dict[str, Any]]]:
        results: List[Optional[Dict[str, Any]]] = [None] * len(texts)
        if not self._family_model or not self._family_tokenizer:
            return results

        batch_size = max(1, int(batch_size))
        try:
            with self._inference_lock:
                for start in range(0, len(texts), batch_size):
                    chunk = list(texts[start : start + batch_size])
                    non_empty = [(idx, text) for idx, text in enumerate(chunk) if text.strip()]
                    if not non_empty:
                        continue
                    inputs = self._family_tokenizer(
                        [text for _, text in non_empty],
                        return_tensors="pt",
                        truncation=True,
                        max_length=512,
                        padding=True,
                    ).to(self._device)
                    with torch.no_grad():
                        outputs = self._family_model(**inputs)
                        probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                    id2label = self._family_model.config.id2label
                    label_indexes = sorted(int(index) for index in id2label.keys())
                    for row, (chunk_index, _) in enumerate(non_empty):
                        all_probs = {
                            str(id2label[index]): float(probabilities[row][index].item())
                            for index in label_indexes
                        }
                        top_idx = int(torch.argmax(probabilities[row]).item())
                        results[start + chunk_index] = {
                            "family": str(id2label[top_idx]),
                            "confidence": float(probabilities[row][top_idx].item()),
                            "all_probabilities": all_probs,
                        }
        except Exception as exc:
            logger.error("Batched model-family detection failed: %s", exc)
        return results

    def analyze_text(self, text: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Full pipeline: 
        1. Check AI vs Human.
        2. If AI > 50%, check Family.
        """
        ai_result = self.detect_ai_human(text)
        
        family_result = None
        # Only burn compute on Family detection if it's actually AI and the model is present
        if ai_result and ai_result.get("is_ai", False) and self._family_model:
            family_result = self.detect_model_family(text)
        
        return ai_result, family_result

    def analyze_texts(
        self, texts: Sequence[str], *, batch_size: int = 16
    ) -> List[Tuple[Optional[Dict], Optional[Dict]]]:
        """Analyze many texts with one tensorized pass per configured chunk."""
        ai_results = self.detect_ai_human_batch(texts, batch_size=batch_size)
        family_results: List[Optional[Dict]] = [None] * len(texts)
        ai_indexes = [
            index
            for index, result in enumerate(ai_results)
            if result and result.get("is_ai", False)
        ]
        if ai_indexes and self._family_model:
            detected = self.detect_model_family_batch(
                [texts[index] for index in ai_indexes], batch_size=batch_size
            )
            for index, result in zip(ai_indexes, detected):
                family_results[index] = result
        return list(zip(ai_results, family_results))

@lru_cache(maxsize=1)
def get_ai_detector() -> AIDetector:
    """Singleton accessor."""
    return AIDetector()
