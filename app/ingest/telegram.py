from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from .errors import DeletedContentError, ExtractionError, InvalidLinkError, PrivateSourceError, RateLimitedError
from .schemas import ExtractedSegment, IngestMetadata
from .text import clean_paragraphs, join_segments, sanitize_text


TELEGRAM_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "DNT": "1",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class TelegramService:
    def __init__(self, timeout: float = 12.0) -> None:
        self.timeout = timeout
        self.headers = TELEGRAM_BROWSER_HEADERS

    def parse_public_link(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        if parsed.netloc.lower() not in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}:
            raise InvalidLinkError("Invalid Telegram URL format.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2 or parts[0] in {"c", "s"}:
            raise InvalidLinkError("Telegram link must be a public t.me/channel/message link.")
        channel, message_id = parts[0], parts[1]
        if not re.fullmatch(r"\d+", message_id):
            raise InvalidLinkError("Telegram link must include a numeric message id.")
        return channel, message_id

    def build_embed_url(self, url: str) -> str:
        channel, message_id = self.parse_public_link(url)
        parsed = urlparse(url.strip())
        return urlunparse((parsed.scheme or "https", parsed.netloc.lower(), f"/{channel}/{message_id}", "", "embed=1", ""))

    async def extract_public_link(self, url: str) -> tuple[IngestMetadata, list[ExtractedSegment], str]:
        channel, message_id = self.parse_public_link(url)
        embed_url = self.build_embed_url(url)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, headers=self.headers) as client:
                response = await client.get(embed_url)
        except httpx.TimeoutException as exc:
            raise ExtractionError("Telegram extraction timed out while loading the public embed view.", status_code=500) from exc
        except httpx.RequestError as exc:
            raise ExtractionError(f"Telegram extraction connection error: {str(exc)}", status_code=500) from exc
        if response.status_code == 429:
            raise RateLimitedError("Telegram rate-limited the ingestion request.")
        if response.status_code in {401, 403}:
            raise PrivateSourceError("This Telegram channel is private or unavailable to public web preview.")
        if response.status_code == 404:
            raise ExtractionError("Telegram returned 404. The post may be deleted or the channel may not be public.", status_code=500)
        if response.status_code >= 400:
            raise ExtractionError(f"Telegram returned HTTP {response.status_code} while loading the public embed view.", status_code=500)
        soup = BeautifulSoup(response.text, "html.parser")
        text_node = soup.select_one("div.tgme_widget_message_text")
        if not text_node:
            raise ExtractionError("Could not locate the message body. Ensure the channel and post are public.", status_code=500)
        author_node = soup.select_one(".tgme_widget_message_author_name")
        time_node = soup.select_one("time")
        extracted_text = sanitize_text(text_node.get_text(separator="\n"))
        if not extracted_text:
            raise ExtractionError("Telegram message body was empty after extraction.", status_code=500)
        timestamp = self._parse_timestamp(time_node.get("datetime") if time_node else None)
        metadata = IngestMetadata(
            platform="telegram",
            author=sanitize_text(author_node.get_text(" ", strip=True)) if author_node else None,
            channel=channel,
            timestamp=timestamp,
            source_url=embed_url,
            message_id=message_id,
            attributes={
                "embed_url": embed_url,
                "views": self._text_or_none(soup.select_one(".tgme_widget_message_views")),
            },
        )
        segments = [
            ExtractedSegment(
                kind="message",
                author=metadata.author,
                timestamp=timestamp,
                permalink=url,
                text=extracted_text,
            )
        ]
        raw_text = join_segments(segment.text for segment in segments)
        return metadata, segments, raw_text

    def extract_bot_update(self, update: dict[str, Any]) -> tuple[IngestMetadata, list[ExtractedSegment], str] | None:
        message = update.get("message") or update.get("channel_post") or update.get("edited_message") or update.get("edited_channel_post")
        if not isinstance(message, dict):
            return None
        forward_origin = message.get("forward_origin") or {}
        chat = message.get("chat") or {}
        source_chat = forward_origin.get("chat") or message.get("forward_from_chat") or chat
        author = self._sender_name(forward_origin.get("sender_user") or message.get("from") or {})
        channel = source_chat.get("username") or source_chat.get("title") or chat.get("username") or chat.get("title")
        text = message.get("text") or message.get("caption") or ""
        paragraphs = clean_paragraphs([text], min_length=50)
        if not paragraphs:
            return None
        timestamp = self._parse_timestamp_from_unix(message.get("date"))
        metadata = IngestMetadata(
            platform="telegram",
            author=author,
            channel=channel,
            timestamp=timestamp,
            source_url=self._bot_source_url(source_chat, message),
            message_id=str(message.get("message_id")) if message.get("message_id") is not None else None,
            attributes={
                "chat_id": chat.get("id"),
                "source_chat_id": source_chat.get("id"),
                "forwarded": bool(forward_origin or message.get("forward_from_chat")),
            },
        )
        segments = [
            ExtractedSegment(
                kind="caption" if message.get("caption") else "message",
                author=author,
                timestamp=timestamp,
                text="\n\n".join(paragraphs),
                permalink=metadata.source_url if metadata.source_url.startswith("http") else None,
            )
        ]
        return metadata, segments, join_segments(segment.text for segment in segments)

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _parse_timestamp_from_unix(self, value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(value))
        except (TypeError, ValueError, OSError):
            return None

    def _sender_name(self, user: dict[str, Any]) -> str | None:
        parts = [user.get("first_name"), user.get("last_name")]
        name = " ".join(part for part in parts if part).strip()
        return name or user.get("username")

    def _bot_source_url(self, chat: dict[str, Any], message: dict[str, Any]) -> str:
        username = chat.get("username")
        message_id = message.get("message_id")
        if username and message_id:
            return f"https://t.me/{username}/{message_id}"
        return f"telegram-bot://{chat.get('id', 'unknown')}/{message_id or 'unknown'}"

    def _text_or_none(self, node: Any) -> str | None:
        if not node:
            return None
        value = sanitize_text(node.get_text(" ", strip=True))
        return value or None
