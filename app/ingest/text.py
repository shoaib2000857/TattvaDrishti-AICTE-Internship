import html
import re
from typing import Iterable


MARKDOWN_PATTERNS = (
    (re.compile(r"```[\s\S]*?```"), " "),
    (re.compile(r"`([^`]+)`"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), r"\1"),
    (re.compile(r"[*_~]{1,3}([^*_~\n]+)[*_~]{1,3}"), r"\1"),
    (re.compile(r"(^|\s)[*_~>#-]{1,4}(\s|$)", re.MULTILINE), " "),
    (re.compile(r"https?://\S+"), " "),
)


def strip_custom_emoji(value: str) -> str:
    return re.sub(
        "["
        "\U0001F1E0-\U0001F1FF"
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\u2600-\u27BF"
        "]+",
        " ",
        value,
    )


def sanitize_text(value: str) -> str:
    text = html.unescape(value or "")
    text = strip_custom_emoji(text)
    for pattern, replacement in MARKDOWN_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def clean_paragraphs(values: Iterable[str], min_length: int = 1) -> list[str]:
    paragraphs = []
    for value in values:
        cleaned = sanitize_text(value)
        if len(cleaned) >= min_length:
            paragraphs.append(cleaned)
    return paragraphs


def join_segments(values: Iterable[str]) -> str:
    return "\n\n".join(clean_paragraphs(values)).strip()
