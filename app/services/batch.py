"""Parsing and normalization for versioned bulk message intake files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ..schemas import (
    BatchDefaults,
    BatchIntakeEnvelope,
    BatchItemError,
    BatchMessage,
    ContentIntake,
    SourceMetadata,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _validate(model: Type[ModelT], value: Any) -> ModelT:
    """Support the Pydantic 1 lockfile and the Pydantic 2 requirements file."""
    validator = getattr(model, "model_validate", None)
    if validator:
        return validator(value)
    return model.parse_obj(value)


def _dump(
    model: BaseModel, *, exclude_none: bool = False, exclude_unset: bool = False
) -> Dict[str, Any]:
    dumper = getattr(model, "model_dump", None)
    if dumper:
        return dumper(exclude_none=exclude_none, exclude_unset=exclude_unset)
    return model.dict(exclude_none=exclude_none, exclude_unset=exclude_unset)


@dataclass(frozen=True)
class BatchRecord:
    index: int
    message_id: str
    intake: ContentIntake
    line_number: Optional[int] = None


@dataclass(frozen=True)
class RejectedBatchRecord:
    index: int
    message_id: Optional[str]
    errors: List[BatchItemError]


@dataclass(frozen=True)
class ParsedBatch:
    batch_id: str
    source_system: str
    collection_id: Optional[str]
    classification_marking: Optional[str]
    records: List[BatchRecord]
    rejected: List[RejectedBatchRecord]
    total: int


class BatchFileError(ValueError):
    """The upload itself is invalid, as opposed to an individual record."""


def envelope_to_parsed(envelope: BatchIntakeEnvelope) -> ParsedBatch:
    batch_id = envelope.batch_id or str(uuid4())
    records = [
        BatchRecord(
            index=index,
            message_id=message.message_id,
            intake=_to_content_intake(
                message,
                envelope.defaults,
                source_system=envelope.source_system,
                collection_id=envelope.collection_id,
                classification_marking=envelope.classification_marking,
            ),
        )
        for index, message in enumerate(envelope.messages)
    ]
    return ParsedBatch(
        batch_id=batch_id,
        source_system=envelope.source_system,
        collection_id=envelope.collection_id,
        classification_marking=envelope.classification_marking,
        records=records,
        rejected=[],
        total=len(records),
    )


def parse_batch_file(
    content: bytes,
    *,
    filename: str,
    source_system: str = "file-upload",
    collection_id: Optional[str] = None,
    classification_marking: Optional[str] = None,
    batch_id: Optional[str] = None,
    max_records: int = 5000,
) -> ParsedBatch:
    """Parse a UTF-8 JSON envelope or newline-delimited JSON message file."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise BatchFileError("Batch files must be UTF-8 encoded.") from error

    lowered_name = (filename or "").lower()
    stripped = text.lstrip()
    if lowered_name.endswith((".jsonl", ".ndjson")):
        return _parse_json_lines(
            text,
            source_system=source_system,
            collection_id=collection_id,
            classification_marking=classification_marking,
            batch_id=batch_id,
            max_records=max_records,
        )
    if lowered_name.endswith(".json") or stripped.startswith("{"):
        return _parse_json_envelope(text, max_records=max_records)
    raise BatchFileError("Unsupported file type. Upload .json, .jsonl, or .ndjson.")


def _parse_json_envelope(text: str, *, max_records: int) -> ParsedBatch:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise BatchFileError(
            f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}."
        ) from error
    if not isinstance(payload, dict):
        raise BatchFileError("A JSON batch must be an object containing a messages array.")

    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise BatchFileError("The JSON batch must contain a messages array.")
    _check_record_count(len(messages), max_records)

    header_payload = dict(payload)
    header_payload["messages"] = []
    try:
        header = _validate(BatchIntakeEnvelope, header_payload)
    except ValidationError as error:
        details = _validation_errors(error, index=0)
        message = "; ".join(item.message for item in details)
        raise BatchFileError(f"Invalid batch envelope: {message}") from error

    records: List[BatchRecord] = []
    rejected: List[RejectedBatchRecord] = []
    for index, raw_message in enumerate(messages):
        record, rejection = _parse_record(
            raw_message,
            index=index,
            defaults=header.defaults,
            source_system=header.source_system,
            collection_id=header.collection_id,
            classification_marking=header.classification_marking,
        )
        if record:
            records.append(record)
        if rejection:
            rejected.append(rejection)

    return ParsedBatch(
        batch_id=header.batch_id or str(uuid4()),
        source_system=header.source_system,
        collection_id=header.collection_id,
        classification_marking=header.classification_marking,
        records=records,
        rejected=rejected,
        total=len(messages),
    )


def _parse_json_lines(
    text: str,
    *,
    source_system: str,
    collection_id: Optional[str],
    classification_marking: Optional[str],
    batch_id: Optional[str],
    max_records: int,
) -> ParsedBatch:
    if not source_system.strip():
        raise BatchFileError("source_system is required for JSON Lines uploads.")

    lines: List[Tuple[int, str]] = [
        (line_number, line)
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    _check_record_count(len(lines), max_records)
    if not lines:
        raise BatchFileError("The batch file contains no message records.")

    defaults = BatchDefaults()
    records: List[BatchRecord] = []
    rejected: List[RejectedBatchRecord] = []
    for index, (line_number, line) in enumerate(lines):
        try:
            raw_message = json.loads(line)
        except json.JSONDecodeError as error:
            rejected.append(
                RejectedBatchRecord(
                    index=index,
                    message_id=None,
                    errors=[
                        BatchItemError(
                            code="invalid_json",
                            message=f"Invalid JSON: {error.msg}.",
                            line_number=line_number,
                        )
                    ],
                )
            )
            continue

        record, rejection = _parse_record(
            raw_message,
            index=index,
            defaults=defaults,
            source_system=source_system,
            collection_id=collection_id,
            classification_marking=classification_marking,
            line_number=line_number,
        )
        if record:
            records.append(record)
        if rejection:
            rejected.append(rejection)

    return ParsedBatch(
        batch_id=batch_id or str(uuid4()),
        source_system=source_system,
        collection_id=collection_id,
        classification_marking=classification_marking,
        records=records,
        rejected=rejected,
        total=len(lines),
    )


def _parse_record(
    raw_message: Any,
    *,
    index: int,
    defaults: BatchDefaults,
    source_system: str,
    collection_id: Optional[str],
    classification_marking: Optional[str],
    line_number: Optional[int] = None,
) -> Tuple[Optional[BatchRecord], Optional[RejectedBatchRecord]]:
    message_id = raw_message.get("message_id") if isinstance(raw_message, dict) else None
    try:
        message = _validate(BatchMessage, raw_message)
    except ValidationError as error:
        return None, RejectedBatchRecord(
            index=index,
            message_id=str(message_id) if message_id is not None else None,
            errors=_validation_errors(error, index=index, line_number=line_number),
        )
    return (
        BatchRecord(
            index=index,
            message_id=message.message_id,
            intake=_to_content_intake(
                message,
                defaults,
                source_system=source_system,
                collection_id=collection_id,
                classification_marking=classification_marking,
            ),
            line_number=line_number,
        ),
        None,
    )


def _to_content_intake(
    message: BatchMessage,
    defaults: BatchDefaults,
    *,
    source_system: str,
    collection_id: Optional[str],
    classification_marking: Optional[str],
) -> ContentIntake:
    metadata: Dict[str, Any] = (
        _dump(defaults.metadata, exclude_none=True) if defaults.metadata else {}
    )
    if message.metadata:
        metadata.update(
            _dump(message.metadata, exclude_none=True, exclude_unset=True)
        )
    metadata.update(
        {
            "message_id": message.message_id,
            "source_system": source_system,
        }
    )
    if message.conversation_id is not None:
        metadata["conversation_id"] = message.conversation_id
    if message.observed_at is not None:
        metadata["observed_at"] = message.observed_at
    if collection_id is not None:
        metadata["collection_id"] = collection_id
    if classification_marking is not None:
        metadata["classification_marking"] = classification_marking
    metadata.setdefault("platform", "unspecified")

    return ContentIntake(
        text=message.text,
        language=message.language or defaults.language,
        source=message.source or defaults.source,
        metadata=_validate(SourceMetadata, metadata),
        tags=message.tags if message.tags is not None else defaults.tags,
    )


def _validation_errors(
    error: ValidationError,
    *,
    index: int,
    line_number: Optional[int] = None,
) -> List[BatchItemError]:
    results: List[BatchItemError] = []
    for detail in error.errors():
        location = ".".join(str(part) for part in detail.get("loc", ())) or None
        results.append(
            BatchItemError(
                code=str(detail.get("type", "validation_error")),
                message=str(detail.get("msg", "Invalid message record.")),
                field=location,
                line_number=line_number,
            )
        )
    return results or [
        BatchItemError(
            code="validation_error",
            message=f"Message record {index} is invalid.",
            line_number=line_number,
        )
    ]


def _check_record_count(count: int, maximum: int) -> None:
    if count == 0:
        raise BatchFileError("The batch contains no message records.")
    if count > maximum:
        raise BatchFileError(
            f"The batch contains {count} records; the configured maximum is {maximum}."
        )
