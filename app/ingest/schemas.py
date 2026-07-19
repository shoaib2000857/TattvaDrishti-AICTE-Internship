from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


Platform = Literal["telegram"]


class TelegramIngestRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_telegram_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return cleaned


class ExtractedSegment(BaseModel):
    kind: Literal["message", "caption"]
    text: str
    author: Optional[str] = None
    timestamp: Optional[datetime] = None
    score: Optional[int] = None
    permalink: Optional[str] = None


class IngestMetadata(BaseModel):
    platform: Platform
    author: Optional[str] = None
    channel: Optional[str] = None
    timestamp: Optional[datetime] = None
    source_url: str
    message_id: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class DetectionPayload(BaseModel):
    ai_probability: Optional[float] = None
    human_probability: Optional[float] = None
    is_ai: Optional[bool] = None
    verdict: str
    model: str
    available: bool


class TelegramTextAnalytics(BaseModel):
    lexical_richness: float
    words_per_sentence: float
    exclamation_markers: int
    total_words: int
    total_characters: int
    total_sentences: int


class IngestResponse(BaseModel):
    platform: Platform
    metadata: IngestMetadata
    segments: List[ExtractedSegment]
    raw_text: str
    sanitized_text: str
    detection: DetectionPayload


class TelegramIngestResponse(BaseModel):
    status: Literal["success"]
    extracted_text: str
    text_length: int
    prediction: str
    prediction_tag: str
    human_confidence: int
    ai_confidence: int
    analytics: TelegramTextAnalytics
    metadata: Dict[str, Any]


class TelegramBotWebhookResponse(BaseModel):
    ok: bool
    processed: int
    results: List[IngestResponse] = Field(default_factory=list)
