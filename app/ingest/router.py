from fastapi import APIRouter, HTTPException, Request

from .analytics import compute_text_analytics
from .errors import IngestError
from .inference import IngestInferenceService
from .schemas import IngestResponse, TelegramBotWebhookResponse, TelegramIngestRequest, TelegramIngestResponse
from .telegram import TelegramService
from .text import sanitize_text


router = APIRouter(prefix="/api/ingest", tags=["social-ingest"])
telegram_service = TelegramService()
inference_service = IngestInferenceService()


def _raise_ingest_error(error: IngestError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={
            "code": error.code,
            "message": error.message,
        },
    )


@router.post("/telegram", response_model=TelegramIngestResponse)
async def ingest_telegram(payload: TelegramIngestRequest) -> TelegramIngestResponse:
    if "t.me/" not in payload.url and "telegram.me/" not in payload.url:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_telegram_url",
                "message": "URL must contain t.me/ or telegram.me/.",
            },
        )
    try:
        metadata, _segments, raw_text = await telegram_service.extract_public_link(payload.url)
        sanitized_text = sanitize_text(raw_text)
        detection = inference_service.detect_ai_human(sanitized_text)
        analytics = compute_text_analytics(sanitized_text, metadata)
        if detection.human_probability is not None:
            human_confidence = int(round(detection.human_probability * 100))
        elif detection.ai_probability is not None:
            human_confidence = 100 - int(round(detection.ai_probability * 100))
        else:
            human_confidence = 0
        human_confidence = max(0, min(100, human_confidence))
        ai_confidence = 100 - human_confidence
        prediction = "AI" if ai_confidence > human_confidence else "Human"
        if detection.available is False:
            prediction = "Unavailable"
            human_confidence = 0
            ai_confidence = 0
        prediction_tag = (
            "AI-likely"
            if prediction == "AI"
            else "Human-likely"
            if prediction == "Human"
            else "Model-unavailable"
        )
        return TelegramIngestResponse(
            status="success",
            extracted_text=sanitized_text,
            text_length=len(sanitized_text),
            prediction=prediction,
            prediction_tag=prediction_tag,
            human_confidence=human_confidence,
            ai_confidence=ai_confidence,
            analytics=analytics,
            metadata={
                "channel": f"@{metadata.channel}" if metadata.channel else None,
                "post_id": f"#{metadata.message_id}" if metadata.message_id else None,
                "model": detection.model,
            },
        )
    except IngestError as error:
        _raise_ingest_error(error)


@router.post("/tg-bot", response_model=TelegramBotWebhookResponse)
async def ingest_telegram_bot(request: Request) -> TelegramBotWebhookResponse:
    try:
        update = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_payload", "message": "Telegram webhook payload must be JSON."},
        ) from exc
    extracted = telegram_service.extract_bot_update(update)
    if not extracted:
        return TelegramBotWebhookResponse(ok=True, processed=0, results=[])
    metadata, segments, raw_text = extracted
    sanitized_text = sanitize_text(raw_text)
    detection = inference_service.detect_ai_human(sanitized_text)
    return TelegramBotWebhookResponse(
        ok=True,
        processed=1,
        results=[
            IngestResponse(
                platform="telegram",
                metadata=metadata,
                segments=segments,
                raw_text=raw_text,
                sanitized_text=sanitized_text,
                detection=detection,
            )
        ],
    )
