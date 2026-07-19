import asyncio
import json
import os

os.environ["DISABLE_AI_MODELS"] = "true"
os.environ["OLLAMA_ENABLED"] = "false"

from app.config import get_settings
from app.models.detection import DetectorEngine
from app.schemas import ContentIntake
from app.services.batch import parse_batch_file
from app.services.orchestrator import AnalysisOrchestrator


def test_json_envelope_applies_defaults_and_preserves_lineage():
    payload = {
        "schema_version": "1.0",
        "batch_id": "batch-17",
        "source_system": "case-exporter",
        "collection_id": "collection-88",
        "classification_marking": "OFFICIAL:SENSITIVE",
        "defaults": {
            "language": "en",
            "source": "chat-export",
            "metadata": {"platform": "messaging", "region": "Delhi"},
            "tags": ["archive"],
        },
        "messages": [
            {
                "message_id": "m-1",
                "conversation_id": "c-4",
                "observed_at": "2026-07-19T09:15:00Z",
                "text": "This is a sufficiently long archived message for batch analysis.",
                "metadata": {"actor_id": "actor-9"},
            }
        ],
    }

    parsed = parse_batch_file(
        json.dumps(payload).encode(), filename="collection.json", max_records=100
    )

    assert parsed.batch_id == "batch-17"
    assert parsed.total == 1
    assert not parsed.rejected
    intake = parsed.records[0].intake
    assert intake.source == "chat-export"
    assert intake.tags == ["archive"]
    assert intake.metadata.message_id == "m-1"
    assert intake.metadata.conversation_id == "c-4"
    assert intake.metadata.collection_id == "collection-88"
    assert intake.metadata.classification_marking == "OFFICIAL:SENSITIVE"
    assert intake.metadata.region == "Delhi"
    assert intake.metadata.actor_id == "actor-9"


def test_json_lines_isolates_invalid_records_and_reports_lines():
    lines = [
        json.dumps(
            {
                "message_id": "valid-1",
                "text": "This valid line contains enough content to enter the pipeline.",
            }
        ),
        "{not-json}",
        json.dumps({"message_id": "short", "text": "too short"}),
    ]

    parsed = parse_batch_file(
        "\n".join(lines).encode(),
        filename="messages.jsonl",
        source_system="unit-test-export",
        max_records=100,
    )

    assert parsed.total == 3
    assert [record.message_id for record in parsed.records] == ["valid-1"]
    assert [record.index for record in parsed.rejected] == [1, 2]
    assert parsed.rejected[0].errors[0].code == "invalid_json"
    assert parsed.rejected[0].errors[0].line_number == 2
    assert parsed.rejected[1].errors[0].field == "text"
    assert parsed.rejected[1].errors[0].line_number == 3


def test_detector_uses_vectorized_ai_batch_interface():
    class FakeAIDetector:
        available = True

        def __init__(self):
            self.calls = []

        def analyze_texts(self, texts, *, batch_size):
            self.calls.append((list(texts), batch_size))
            return [
                (
                    {
                        "ai_probability": 0.8,
                        "human_probability": 0.2,
                        "is_ai": True,
                    },
                    {
                        "family": "test-family",
                        "confidence": 0.9,
                        "all_probabilities": {"test-family": 0.9},
                    },
                )
                for _ in texts
            ]

    detector = DetectorEngine()
    fake = FakeAIDetector()
    detector._ai_detector = fake
    detector._ollama_client = None
    intakes = [
        ContentIntake(text=f"Message {index} has sufficient length for batch testing.")
        for index in range(3)
    ]

    results = detector.detect_batch(
        intakes, ai_batch_size=2, parallelism=2, ollama_parallelism=1
    )

    assert len(fake.calls) == 1
    assert fake.calls[0][1] == 2
    assert len(results) == 3
    assert all(result[2].ai_probability == 0.8 for result in results)
    assert all(result[2].model_family == "test-family" for result in results)


def test_orchestrator_batch_persists_batch_and_external_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/batch.db")
    get_settings.cache_clear()
    orchestrator = AnalysisOrchestrator()
    records = [
        (
            "external-1",
            ContentIntake(
                text="A sufficiently long message that can be persisted in a batch case.",
                source="test",
            ),
        ),
        (
            "external-2",
            ContentIntake(
                text="Another sufficiently long message that exercises ordered persistence.",
                source="test",
            ),
        ),
    ]

    outcomes = asyncio.run(
        orchestrator.process_batch(records, batch_id="batch-persistence-test")
    )

    assert len(outcomes) == 2
    assert all(error is None for _, error in outcomes)
    assert all(result.graph_summary.node_count == 3 for result, _ in outcomes)
    for external_id, (result, _) in zip(("external-1", "external-2"), outcomes):
        stored = orchestrator.db.fetch_case(result.intake_id)
        assert stored["batch_id"] == "batch-persistence-test"
        assert stored["external_message_id"] == external_id
