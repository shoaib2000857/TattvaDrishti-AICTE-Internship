"""Read-only, structured evidence review for a selected analyst case."""

from __future__ import annotations

from typing import Any, Iterable

from ..schemas import EvidenceItem, EvidenceReview
from ..storage.database import Database
from .narrative_intel import NarrativeIntelEngine


class EvidenceReviewService:
    """Turn already-stored findings into balanced review language.

    This service deliberately never runs detector inference and never changes a
    stored score. It surfaces supporting signals separately from missing or
    inconclusive signals so that a low signal is not presented as clearance.
    """

    def __init__(self, database: Database, narratives: NarrativeIntelEngine) -> None:
        self.db = database
        self.narratives = narratives

    def review(self, intake_id: str) -> EvidenceReview:
        case = self.db.fetch_case(intake_id)
        if not case:
            raise ValueError("Case not found.")

        breakdown = case.get("breakdown") or {}
        provenance = case.get("provenance") or {}
        metadata = case.get("metadata") or {}
        heuristics = [str(item) for item in (breakdown.get("heuristics") or [])]
        supporting: list[EvidenceItem] = []
        counter: list[EvidenceItem] = []
        uncertainties: list[EvidenceItem] = []

        behavioral = self._number(breakdown.get("behavioral_score"))
        if behavioral is not None and behavioral >= 0.25:
            supporting.append(self._item(
                "behavioral", "Behavioral manipulation indicators were elevated",
                "Stored behavioural analysis recorded urgency, action pressure, or contextual cues requiring review.",
                "strong" if behavioral >= 0.5 else "moderate", "behavioral_analysis",
            ))
        elif behavioral is not None:
            counter.append(self._item(
                "behavioral", "Behavioural manipulation signal was limited",
                "The stored behavioural signal does not strongly add to the current concern.",
                "limited", "behavioral_analysis",
            ))
        else:
            uncertainties.append(self._item(
                "behavioral", "Behavioural analysis is unavailable",
                "No stored behavioural score is available for this case.",
                "limited", "behavioral_analysis",
            ))

        self._append_heuristic_evidence(heuristics, supporting)

        semantic = self._number(breakdown.get("ollama_risk"))
        if semantic is None:
            uncertainties.append(self._item(
                "semantic_risk", "Semantic-risk analysis is unavailable",
                "No stored semantic-risk result is available for this case.",
                "limited", "semantic_risk",
            ))
        elif semantic >= 0.6:
            supporting.append(self._item(
                "semantic_risk", "Semantic-risk signal was elevated",
                "The stored semantic-risk module returned an elevated review signal.",
                "strong" if semantic >= 0.75 else "moderate", "semantic_risk",
            ))
        elif semantic <= 0.4:
            counter.append(self._item(
                "semantic_risk", "Semantic-risk signal was not elevated",
                "This module does not strongly support the concern; its result alone does not resolve the case.",
                "limited", "semantic_risk",
            ))

        ai_probability = self._number(breakdown.get("ai_probability"))
        if ai_probability is None:
            uncertainties.append(self._item(
                "ai_origin", "AI-origin analysis is unavailable",
                "No stored AI-origin estimate is available for this case.",
                "limited", "ai_detector",
            ))
        elif ai_probability >= 0.7:
            supporting.append(self._item(
                "ai_origin", "AI-origin pattern was elevated",
                "The stored AI-origin estimate is elevated and contributes to prioritization, not a conclusion about truth.",
                "strong" if ai_probability >= 0.85 else "moderate", "ai_detector",
            ))
        else:
            counter.append(self._item(
                "ai_origin", "AI-origin signal is inconclusive",
                "AI-origin analysis does not strongly indicate machine-generated text; this is not evidence the message is trustworthy.",
                "limited", "ai_detector",
            ))

        linguistic = self._number(breakdown.get("linguistic_score"))
        if linguistic is not None and linguistic >= 0.65:
            supporting.append(self._item(
                "stylometric", "Stylometric signal was elevated",
                "Stored writing-pattern analysis contributed an elevated signal.",
                "moderate", "stylometric_analysis",
            ))
        elif linguistic is not None and linguistic <= 0.35:
            counter.append(self._item(
                "stylometric", "Stylometric signal was limited",
                "Writing-pattern analysis does not strongly add to the current concern.",
                "limited", "stylometric_analysis",
            ))

        try:
            similar = self.narratives.find_similar_messages(
                intake_id, scope="all_cases", limit=100
            )
        except ValueError:
            similar = None
        if similar and similar.count:
            supporting.append(self._item(
                "narrative_similarity", "Related analysed messages were observed",
                f"{similar.count} stored message{'s' if similar.count != 1 else ''} met the configured similarity threshold.",
                "strong" if similar.count >= 5 else "moderate", "narrative_similarity",
            ))
        else:
            uncertainties.append(self._item(
                "narrative_similarity", "No strong related-message result is currently available",
                "No stored message met the configured similarity threshold in the available analysed cases.",
                "limited", "narrative_similarity",
            ))

        related_urls = metadata.get("related_urls") or []
        if related_urls:
            uncertainties.append(self._item(
                "source_context", "External links require independent verification",
                f"{len(related_urls)} stored external link{'s' if len(related_urls) != 1 else ''} are associated with this case; no URL verdict is inferred here.",
                "moderate", "source_metadata",
            ))
        else:
            uncertainties.append(self._item(
                "source_context", "No external URL evidence is available",
                "The stored case does not include related URLs for independent review.",
                "limited", "source_metadata",
            ))

        if provenance.get("watermark_present") or provenance.get("signature_valid"):
            uncertainties.append(self._item(
                "provenance", "A provenance marker was recorded",
                "Integrity markers can describe asset history; they do not establish factual accuracy or intent.",
                "limited", "provenance",
            ))
        else:
            uncertainties.append(self._item(
                "provenance", "Origin or provenance information is unavailable",
                "The absence of a stored provenance marker does not by itself indicate manipulation.",
                "limited", "provenance",
            ))

        disagreement = self._disagreement(breakdown)
        if disagreement:
            uncertainties.append(self._item(
                "model_disagreement", "Signals disagree",
                disagreement, "moderate", "signal_comparison",
            ))

        return EvidenceReview(
            intake_id=intake_id,
            supporting=self._deduplicate(supporting),
            counter=self._deduplicate(counter),
            uncertainties=self._deduplicate(uncertainties),
            signals_disagree=bool(disagreement),
            disagreement_summary=disagreement,
        )

    @staticmethod
    def _item(type_: str, label: str, description: str, strength: str, source: str) -> EvidenceItem:
        return EvidenceItem(type=type_, label=label, description=description, strength=strength, source=source)

    def _append_heuristic_evidence(
        self, heuristics: Iterable[str], supporting: list[EvidenceItem]
    ) -> None:
        joined = "\n".join(heuristics).lower()
        rules = (
            ("emotional manipulation", "Urgency or emotional-pressure language detected", "Stored behavioural analysis recorded emotional or urgency cues.", "behavioral_analysis"),
            ("call-to-action", "Call-to-action language detected", "Stored behavioural analysis recorded a call-to-action pattern.", "behavioral_analysis"),
            ("external links", "Multiple external links were recorded", "Stored heuristics recorded multiple external links; this does not classify any link as harmful.", "url_heuristic"),
            ("high-risk", "Source context was flagged for review", "A stored platform or analyst-tag heuristic added contextual concern.", "source_context"),
            ("phrase repetition", "Repeated phrasing was detected", "Stored stylometric heuristics recorded repeated phrasing.", "stylometric_analysis"),
        )
        for phrase, label, description, source in rules:
            if phrase in joined:
                supporting.append(self._item("heuristic", label, description, "moderate", source))

    def _disagreement(self, breakdown: dict[str, Any]) -> str | None:
        signals = {
            "Semantic risk": self._number(breakdown.get("ollama_risk")),
            "AI-origin": self._number(breakdown.get("ai_probability")),
            "Behavioural": self._number(breakdown.get("behavioral_score")),
            "Stylometry": self._number(breakdown.get("linguistic_score")),
        }
        available = {label: score for label, score in signals.items() if score is not None}
        elevated = [label for label, score in available.items() if score >= 0.65]
        limited = [label for label, score in available.items() if score <= 0.35]
        if elevated and limited:
            detail = "; ".join(
                f"{label}: {score:.0%}" for label, score in available.items()
            )
            return f"The stored modules do not fully agree ({detail}). Human review is recommended."
        return None

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if 0.0 <= numeric <= 1.0 else None

    @staticmethod
    def _deduplicate(items: Iterable[EvidenceItem]) -> list[EvidenceItem]:
        seen: set[str] = set()
        unique: list[EvidenceItem] = []
        for item in items:
            if item.label not in seen:
                seen.add(item.label)
                unique.append(item)
        return unique
