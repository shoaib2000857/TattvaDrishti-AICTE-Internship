import re

from .schemas import IngestMetadata, TelegramTextAnalytics


WORD_PATTERN = re.compile(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b")
SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]+")
EXCLAMATION_PATTERN = re.compile(r"!")


def compute_text_analytics(text: str, metadata: IngestMetadata) -> TelegramTextAnalytics:
    words = WORD_PATTERN.findall(text.lower())
    word_count = len(words)
    unique_words = len(set(words))
    sentences = [segment.strip() for segment in SENTENCE_BOUNDARY_PATTERN.split(text)]
    sentences = [segment for segment in sentences if WORD_PATTERN.search(segment)]
    sentence_count = len(sentences)
    lexical_richness = unique_words / word_count if word_count else 0.0
    words_per_sentence = word_count / sentence_count if sentence_count else 0.0
    return TelegramTextAnalytics(
        lexical_richness=round(lexical_richness * 100, 2),
        words_per_sentence=round(words_per_sentence, 2),
        exclamation_markers=len(EXCLAMATION_PATTERN.findall(text)),
        total_words=word_count,
        total_characters=len(text),
        total_sentences=sentence_count,
    )
