import os

os.environ["DISABLE_AI_MODELS"] = "true"
os.environ["OLLAMA_ENABLED"] = "false"

from app.config import get_settings
from app.schemas import ContentIntake, SourceMetadata
from app.services.evidence_review import EvidenceReviewService
from app.services.narrative_intel import NarrativeIntelEngine
from app.storage.database import Database


def _services(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/investigation.db")
    monkeypatch.setenv("SIMILAR_MESSAGE_THRESHOLD", "0.20")
    get_settings.cache_clear()
    database = Database()
    narratives = NarrativeIntelEngine(database)
    return database, narratives, EvidenceReviewService(database, narratives)


def _store_case(database, narratives, intake_id, text, *, batch_id=None, score=0.72, breakdown=None):
    metadata = {
        "platform": "telegram",
        "region": "Hyderabad",
        "actor_id": f"actor-{intake_id}",
        "related_urls": [],
    }
    database.save_case(
        intake_id=intake_id,
        raw_text=text,
        classification="high-risk" if score >= 0.6 else "low-risk",
        composite_score=score,
        metadata=metadata,
        breakdown=breakdown or {
            "linguistic_score": 0.7,
            "behavioral_score": 0.6,
            "ai_probability": 0.75,
            "ollama_risk": 0.7,
            "stylometric_anomalies": {},
            "heuristics": ["Detected 1 call-to-action patterns (common in influence ops)."],
        },
        provenance={
            "watermark_present": False,
            "signature_valid": False,
            "validation_notes": [],
            "content_hash": f"hash-{intake_id}",
        },
        batch_id=batch_id,
        external_message_id=f"external-{intake_id}",
    )
    narratives.ingest(
        intake_id,
        ContentIntake(
            text=text,
            source="unit-test",
            metadata=SourceMetadata(**metadata),
            tags=["banking-withdrawal"],
        ),
        "high-risk" if score >= 0.6 else "low-risk",
        score,
        __import__("datetime").datetime.utcnow(),
    )


def test_similar_messages_excludes_source_orders_and_honors_limit(tmp_path, monkeypatch):
    database, narratives, _ = _services(tmp_path, monkeypatch)
    source = "URGENT: Bharat Vikas Bank withdrawals will stop at 6 PM. Withdraw money immediately and forward this message."
    _store_case(database, narratives, "source", source, batch_id="batch-a")
    _store_case(database, narratives, "closest", "Urgent Bharat Vikas Bank withdrawal notice: withdraw funds immediately and forward this update.", batch_id="batch-a")
    _store_case(database, narratives, "other", "Bharat Vikas Bank says withdrawals may stop tonight. Forward this urgent notice immediately.", batch_id="batch-a")

    all_results = narratives.find_similar_messages("source", scope="current_batch")
    response = narratives.find_similar_messages("source", scope="current_batch", limit=1)

    assert response.scope == "current_batch"
    assert response.count == 1
    assert response.results[0].intake_id != "source"
    assert response.results[0].similarity >= 0.20
    assert response.results[0].matching_reasons
    assert response.results[0].classification == "high-risk"
    assert len({result.intake_id for result in all_results.results}) == all_results.count
    assert [result.similarity for result in all_results.results] == sorted(
        (result.similarity for result in all_results.results), reverse=True
    )


def test_similar_messages_batch_scope_and_no_result_state(tmp_path, monkeypatch):
    database, narratives, _ = _services(tmp_path, monkeypatch)
    _store_case(database, narratives, "source", "Urgent bank withdrawal message asks people to forward it immediately.", batch_id="batch-a")
    _store_case(database, narratives, "outside", "Urgent bank withdrawal message asks people to forward it immediately.", batch_id="batch-b")

    in_batch = narratives.find_similar_messages("source", scope="current_batch")
    all_cases = narratives.find_similar_messages("source", scope="all_cases")

    assert in_batch.count == 0
    assert "No strongly related" in in_batch.message
    assert all_cases.count == 1
    assert all_cases.results[0].intake_id == "outside"


def test_similar_messages_missing_reference_is_clean_error(tmp_path, monkeypatch):
    _, narratives, _ = _services(tmp_path, monkeypatch)
    try:
        narratives.find_similar_messages("missing")
        assert False, "missing case should not be silently searched"
    except ValueError as error:
        assert "Unknown narrative" in str(error)


def test_evidence_review_balances_stored_signals_without_changing_score(tmp_path, monkeypatch):
    database, narratives, evidence = _services(tmp_path, monkeypatch)
    breakdown = {
        "linguistic_score": 0.72,
        "behavioral_score": 0.7,
        "ai_probability": 0.2,
        "ollama_risk": 0.82,
        "stylometric_anomalies": {},
        "heuristics": [
            "Emotional manipulation via 3 urgency terms, 0 valence words, and 1 exclamations.",
            "Detected 1 call-to-action patterns (common in influence ops).",
        ],
    }
    _store_case(
        database,
        narratives,
        "source",
        "URGENT: withdraw money immediately and forward this banking message.",
        batch_id="batch-a",
        score=0.81,
        breakdown=breakdown,
    )
    _store_case(database, narratives, "related", "Urgent banking message: withdraw funds and forward immediately.", batch_id="batch-a")

    before = database.fetch_case("source")["composite_score"]
    review = evidence.review("source")
    after = database.fetch_case("source")["composite_score"]

    assert any(item.source == "behavioral_analysis" for item in review.supporting)
    assert any("AI-origin signal is inconclusive" == item.label for item in review.counter)
    assert review.signals_disagree is True
    assert any(item.label == "Signals disagree" for item in review.uncertainties)
    assert before == after


def test_evidence_review_treats_missing_signals_as_uncertainty(tmp_path, monkeypatch):
    database, narratives, evidence = _services(tmp_path, monkeypatch)
    _store_case(
        database,
        narratives,
        "minimal",
        "A sufficiently long neutral message retained for case evidence review testing.",
        score=0.2,
        breakdown={
            "linguistic_score": 0.2,
            "behavioral_score": None,
            "ai_probability": None,
            "ollama_risk": None,
            "stylometric_anomalies": {},
            "heuristics": [],
        },
    )

    review = evidence.review("minimal")

    labels = {item.label for item in review.uncertainties}
    assert "AI-origin analysis is unavailable" in labels
    assert "Semantic-risk analysis is unavailable" in labels
    assert "Origin or provenance information is unavailable" in labels
    assert not any("safe" in item.description.lower() for item in review.counter + review.uncertainties)
