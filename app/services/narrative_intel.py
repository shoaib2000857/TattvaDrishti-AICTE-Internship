"""Persistent narrative similarity, propagation, origin, and war-room analysis."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Sequence

import networkx as nx

from ..config import get_settings
from ..schemas import (
    ContentIntake,
    CopilotRequest,
    CopilotResponse,
    EvidenceCitation,
    Hotspot,
    NarrativeMatch,
    NarrativeObservation,
    NarrativeTrace,
    OriginAssessment,
    TimelineBucket,
    WarRoomNarrative,
    WarRoomSnapshot,
)
from ..storage.database import Database


_WORD_RE = re.compile(r"[\w#@'-]{2,}", re.UNICODE)
_ENTITY_RE = re.compile(r"(?:https?://\S+|@[\w_]+|#[\w_]+|\b[A-Z][a-z]{2,}\b)")
_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "has",
    "was", "were", "are", "will", "would", "could", "should", "into", "your",
    "you", "they", "their", "about", "after", "before", "when", "where", "what",
    "which", "while", "been", "being", "than", "then", "also", "just", "over",
}
_CONCEPTS = {
    "demonstration": "protest", "protests": "protest", "demonstrators": "protest",
    "rally": "protest", "march": "protest", "unrest": "protest",
    "ballots": "election", "voting": "election", "votes": "election", "polls": "election",
    "fabricated": "fake", "forged": "fake", "hoax": "fake", "false": "fake",
    "authorities": "government", "officials": "government", "ministry": "government",
    "police": "law-enforcement", "cops": "law-enforcement", "officers": "law-enforcement",
    "detained": "detain", "detention": "detain", "arrested": "detain", "custody": "detain",
    "organisers": "organizer", "organizers": "organizer", "leaders": "organizer",
    "dawn": "early", "sunrise": "early", "daybreak": "early", "morning": "early",
    "railway": "station", "main": "central",
    "shutdown": "offline", "disabled": "offline", "disabling": "offline", "shut": "offline",
    "midday": "noon", "12": "noon",
    "coordinate": "organize", "coordinating": "organize", "coordination": "organize",
    "communicate": "organize", "communication": "organize", "messaging": "organize",
    "participants": "protest", "demonstrators": "protest",
    "explosion": "blast", "bombing": "blast", "detonation": "blast",
    "dead": "casualty", "killed": "casualty", "deaths": "casualty", "fatalities": "casualty",
    "forward": "amplify", "share": "amplify", "repost": "amplify", "viral": "amplify",
    "secret": "concealment", "hidden": "concealment", "covered": "concealment",
}


def _utc(value: Any = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


class NarrativeIntelEngine:
    def __init__(self, database: Database) -> None:
        self.db = database
        self.settings = get_settings()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._token_index: Dict[str, set[str]] = defaultdict(set)
        self._tag_index: Dict[str, set[str]] = defaultdict(set)
        self._entity_index: Dict[str, set[str]] = defaultdict(set)
        for record in self.db.fetch_narrative_observations(
            self.settings.narrative_candidate_limit
        ):
            self._index_record(record)

    def ingest(
        self,
        intake_id: str,
        intake: ContentIntake,
        classification: str,
        composite_score: float,
        submitted_at: datetime,
    ) -> list[NarrativeMatch]:
        metadata = intake.metadata
        platform = (metadata.platform if metadata else None) or intake.source or "unknown"
        observed_at = (metadata.observed_at if metadata else None) or submitted_at
        record = {
            "intake_id": intake_id,
            "text": intake.text,
            "platform": platform.strip().lower(),
            "actor_id": metadata.actor_id if metadata else None,
            "region": metadata.region if metadata else None,
            "source": intake.source,
            "tags": sorted({tag.strip().lower() for tag in (intake.tags or []) if tag.strip()}),
            "observed_at": _utc(observed_at).isoformat(),
            "classification": classification,
            "composite_score": float(composite_score),
            "features": self._features(intake.text, intake.tags or []),
        }
        candidates = [
            self._records[candidate_id]
            for candidate_id in self._candidate_ids(record["features"])
            if candidate_id in self._records
        ]
        matches: list[NarrativeMatch] = []
        for candidate in candidates:
            score = self._similarity(record["features"], candidate["features"])
            if score < self.settings.narrative_similarity_threshold:
                continue
            relationship = self._relationship(score)
            matches.append(self._match(candidate, score, relationship))
        matches.sort(key=lambda item: item.similarity, reverse=True)
        matches = matches[: self.settings.narrative_neighbors_per_item]
        for match in matches:
            self.db.save_narrative_edge(
                intake_id, match.intake_id, match.similarity, match.relationship
            )
        self.db.save_narrative_observation(record)
        self._index_record(record)
        return matches

    def backfill_existing_cases(self) -> int:
        """Make pre-upgrade cases searchable without re-running AI detection."""
        if self.db.fetch_narrative_observations(1):
            return 0
        count = 0
        for case in self.db.fetch_cases(self.settings.narrative_candidate_limit):
            metadata = case.get("metadata") or {}
            intake = ContentIntake(
                text=case["raw_text"],
                source=metadata.get("source_system") or "historical-case",
                metadata=metadata,
                tags=metadata.get("tags") or [],
            )
            self.ingest(
                case["intake_id"], intake, case["classification"],
                case["composite_score"], _utc(case["created_at"]),
            )
            count += 1
        return count

    def similar(self, intake_id: str, limit: int = 20) -> list[NarrativeMatch]:
        records = self._records_by_id()
        if intake_id not in records:
            raise ValueError("Unknown narrative intake reference.")
        results: list[NarrativeMatch] = []
        for edge in self.db.fetch_narrative_edges(intake_id):
            other_id = None
            if edge["source"] == intake_id:
                other_id = edge["target"]
            elif edge["target"] == intake_id:
                other_id = edge["source"]
            if other_id and other_id in records:
                results.append(
                    self._match(records[other_id], edge["similarity"], edge["relationship"])
                )
        results.sort(key=lambda item: item.similarity, reverse=True)
        return results[: max(1, min(limit, 100))]

    def trace(self, intake_id: str) -> NarrativeTrace:
        records = self._records_by_id()
        if intake_id not in records:
            raise ValueError("Unknown narrative intake reference.")
        graph = self._similarity_graph(records)
        component = nx.node_connected_component(graph, intake_id)
        ordered = sorted((records[item] for item in component), key=lambda item: _utc(item["observed_at"]))
        edges = self.db.fetch_narrative_edges()
        edge_scores = {
            frozenset((edge["source"], edge["target"])): edge["similarity"] for edge in edges
        }
        observations: list[NarrativeObservation] = []
        previous_id: Optional[str] = None
        for record in ordered:
            similarity = edge_scores.get(frozenset((previous_id, record["intake_id"]))) if previous_id else None
            observations.append(self._observation(record, similarity))
            previous_id = record["intake_id"]
        origin_record = ordered[0]
        metadata_fields = sum(bool(origin_record.get(key)) for key in ("actor_id", "region", "platform"))
        origin_confidence = min(0.95, 0.45 + 0.1 * metadata_fields + 0.03 * min(len(ordered), 5))
        first_seen = _utc(origin_record["observed_at"])
        last_seen = _utc(ordered[-1]["observed_at"])
        reference_time = min(datetime.now(timezone.utc), last_seen + timedelta(seconds=1))
        velocity, acceleration = self._velocity(ordered, reference_time)
        return NarrativeTrace(
            narrative_id=self._cluster_id(component),
            label=self._cluster_label(ordered),
            query_intake_id=intake_id,
            origin=OriginAssessment(
                intake_id=origin_record["intake_id"],
                platform=origin_record["platform"],
                actor_id=origin_record.get("actor_id"),
                region=origin_record.get("region"),
                observed_at=first_seen,
                confidence=round(origin_confidence, 3),
                basis=[
                    "Earliest timestamp in the collected narrative cluster",
                    f"Compared across {len(ordered)} semantically related observations",
                    f"Observed on {len({item['platform'] for item in ordered})} platform(s)",
                ],
            ),
            platforms=list(dict.fromkeys(item["platform"] for item in ordered)),
            actors=sorted({item["actor_id"] for item in ordered if item.get("actor_id")}),
            regions=sorted({item["region"] for item in ordered if item.get("region")}),
            observations=observations,
            matches=self.similar(intake_id, limit=100),
            first_seen=first_seen,
            last_seen=last_seen,
            velocity_per_hour=velocity,
            acceleration=acceleration,
        )

    def war_room(
        self,
        *,
        title: str = "Live Influence Incident",
        window_hours: int = 24,
        query: Optional[str] = None,
    ) -> WarRoomSnapshot:
        generated_at = datetime.now(timezone.utc)
        all_records = self._records_by_id()
        newest = max(
            (_utc(item["observed_at"]) for item in all_records.values()),
            default=generated_at,
        )
        # Imported incident files can be historical. Anchor their analytic
        # window to the collection rather than hiding them as "too old".
        reference_time = min(generated_at, newest + timedelta(seconds=1))
        cutoff = reference_time - timedelta(hours=window_hours)
        records = {
            key: record for key, record in all_records.items()
            if _utc(record["observed_at"]) >= cutoff and self._query_match(record, query)
        }
        graph = self._similarity_graph(records)
        narratives: list[WarRoomNarrative] = []
        for component in nx.connected_components(graph):
            cluster_records = sorted(
                (records[item] for item in component), key=lambda item: _utc(item["observed_at"])
            )
            velocity, acceleration = self._velocity(cluster_records, reference_time)
            recent = sum(
                _utc(item["observed_at"]) >= reference_time - timedelta(hours=2)
                for item in cluster_records
            )
            status = "accelerating" if acceleration >= 0.5 and recent >= 2 else "emerging" if recent and len(cluster_records) <= 3 else "stable"
            narratives.append(
                WarRoomNarrative(
                    narrative_id=self._cluster_id(component),
                    label=self._cluster_label(cluster_records),
                    posts=len(cluster_records),
                    platforms=list(dict.fromkeys(item["platform"] for item in cluster_records)),
                    actors=len({item["actor_id"] for item in cluster_records if item.get("actor_id")}),
                    average_risk=round(sum(item["composite_score"] for item in cluster_records) / len(cluster_records), 3),
                    velocity_per_hour=velocity,
                    acceleration=acceleration,
                    status=status,
                    first_seen=_utc(cluster_records[0]["observed_at"]),
                    last_seen=_utc(cluster_records[-1]["observed_at"]),
                )
            )
        narratives.sort(key=lambda item: (item.posts, item.average_risk), reverse=True)
        records_list = list(records.values())
        actor_risk: Dict[str, list[float]] = defaultdict(list)
        region_risk: Dict[str, list[float]] = defaultdict(list)
        platforms: Counter[str] = Counter()
        for record in records_list:
            platforms[record["platform"]] += 1
            if record.get("actor_id"):
                actor_risk[record["actor_id"]].append(record["composite_score"])
            if record.get("region"):
                region_risk[record["region"]].append(record["composite_score"])
        hotspots = sorted(
            (Hotspot(region=region, posts=len(scores), average_risk=round(sum(scores) / len(scores), 3)) for region, scores in region_risk.items()),
            key=lambda item: (item.posts, item.average_risk), reverse=True,
        )[:10]
        timeline = self._timeline(records_list, cutoff, reference_time)
        return WarRoomSnapshot(
            title=title,
            generated_at=generated_at,
            window_hours=window_hours,
            posts_analyzed=len(records_list),
            major_narratives=sum(item.posts >= self.settings.narrative_major_cluster_size for item in narratives),
            emerging_clusters=sum(item.status == "emerging" for item in narratives),
            high_priority_accounts=sum(max(scores) >= 0.7 for scores in actor_risk.values()),
            accelerating_narratives=sum(item.status == "accelerating" for item in narratives),
            narratives=narratives[:20],
            hotspots=hotspots,
            timeline=timeline,
            platforms=dict(platforms.most_common()),
        )

    def copilot(self, request: CopilotRequest) -> CopilotResponse:
        trace = None
        if request.intake_id:
            trace = self.trace(request.intake_id)
        elif request.narrative_id:
            records = self._records_by_id()
            graph = self._similarity_graph(records)
            for component in nx.connected_components(graph):
                if self._cluster_id(component) == request.narrative_id:
                    trace = self.trace(next(iter(component)))
                    break
        if trace is None:
            return CopilotResponse(
                answer="I need a case or narrative selection before I can answer from evidence.",
                citations=[], scope="no evidence selected", grounded=False,
                limitations=["No case evidence was supplied."],
            )
        question = request.question.lower()
        citations = [
            EvidenceCitation(
                evidence_id=item.intake_id,
                description=f"{item.platform}: {item.text_preview}",
                observed_at=item.observed_at,
            )
            for item in trace.observations[:8]
        ]
        if any(word in question for word in ("why", "flag", "evidence", "link")):
            high = [item for item in trace.observations if item.composite_score >= 0.6]
            answer = (
                f"This narrative contains {len(trace.observations)} related observations across "
                f"{len(trace.platforms)} platforms and {len(trace.actors)} identified accounts. "
                f"{len(high)} observations are high-risk; the strongest linkage is semantic similarity "
                f"plus the ordered cross-platform timeline from {trace.first_seen:%d %b %H:%M} UTC."
            )
        elif any(phrase in question for phrase in ("last 2", "changed", "accelerat")):
            answer = (
                f"Current velocity is {trace.velocity_per_hour:.2f} posts/hour with acceleration "
                f"{trace.acceleration:+.2f}. The latest observation was on "
                f"{trace.observations[-1].platform} at {trace.last_seen:%d %b %H:%M} UTC."
            )
        elif any(word in question for word in ("origin", "first", "source")):
            origin = trace.origin
            answer = (
                f"The earliest collected observation is {origin.intake_id} on {origin.platform} "
                f"at {origin.observed_at:%d %b %Y %H:%M} UTC"
                f"{f' by {origin.actor_id}' if origin.actor_id else ''}. Confidence is "
                f"{origin.confidence:.0%}; this is an earliest-observed lead, not proof of authorship."
            )
        elif any(word in question for word in ("compare", "yesterday", "version")):
            first, latest = trace.observations[0], trace.observations[-1]
            answer = (
                f"The narrative moved from {first.platform} to {latest.platform} between "
                f"{first.observed_at:%d %b %H:%M} and {latest.observed_at:%d %b %H:%M} UTC. "
                f"Risk changed from {first.composite_score:.0%} to {latest.composite_score:.0%}; "
                f"review the cited texts for wording changes."
            )
        else:
            answer = (
                f"Evidence summary: {trace.label} has {len(trace.observations)} observations across "
                f"{', '.join(trace.platforms)}, with {len(trace.actors)} identified accounts and "
                f"current velocity {trace.velocity_per_hour:.2f} posts/hour."
            )
        return CopilotResponse(
            answer=answer,
            citations=citations,
            scope=f"narrative {trace.narrative_id}",
            limitations=[
                "Answer uses only evidence stored in this narrative cluster.",
                "Origin means earliest collected observation, not verified authorship.",
            ],
        )

    def _records_by_id(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._records)

    def _index_record(self, record: Dict[str, Any]) -> None:
        intake_id = record["intake_id"]
        self._records[intake_id] = record
        features = record.get("features", {})
        for token in features.get("tokens", {}):
            self._token_index[token].add(intake_id)
        for tag in features.get("tags", []):
            self._tag_index[tag].add(intake_id)
        for entity in features.get("entities", []):
            self._entity_index[entity].add(intake_id)

    def _candidate_ids(self, features: Dict[str, Any]) -> list[str]:
        """Use sparse lexical/entity indexes instead of an O(batch²) full scan."""
        candidates: set[str] = set()
        ranked_tokens = sorted(
            features.get("tokens", {}),
            key=lambda token: len(self._token_index.get(token, ())),
        )[:24]
        for token in ranked_tokens:
            candidates.update(self._token_index.get(token, ()))
        for tag in features.get("tags", []):
            candidates.update(self._tag_index.get(tag, ()))
        for entity in features.get("entities", []):
            candidates.update(self._entity_index.get(entity, ()))
        if not candidates:
            candidates.update(list(self._records)[:100])
        ordered = sorted(
            candidates,
            key=lambda item: _utc(self._records[item]["observed_at"]),
            reverse=True,
        )
        return ordered[: self.settings.narrative_candidates_per_item]

    def _similarity_graph(self, records: Dict[str, Dict[str, Any]]) -> nx.Graph:
        graph = nx.Graph()
        graph.add_nodes_from(records)
        for edge in self.db.fetch_narrative_edges():
            if edge["source"] in records and edge["target"] in records:
                graph.add_edge(edge["source"], edge["target"], **edge)
        return graph

    def _features(self, text: str, tags: Sequence[str]) -> Dict[str, Any]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        words = []
        for raw in _WORD_RE.findall(normalized):
            word = raw.strip("#@'-")
            if not word or word in _STOPWORDS:
                continue
            word = _CONCEPTS.get(word, self._stem(word))
            words.append(word)
        counts = Counter(words)
        bigrams = Counter(f"{a}_{b}" for a, b in zip(words, words[1:]))
        chars = Counter(normalized[index:index + 4] for index in range(max(0, len(normalized) - 3)))
        entities = sorted({item.lower().rstrip(".,:;!?") for item in _ENTITY_RE.findall(text)})
        return {
            "normalized": normalized,
            "tokens": dict(counts),
            "bigrams": dict(bigrams),
            "chars": dict(chars.most_common(400)),
            "entities": entities,
            "tags": sorted({tag.lower() for tag in tags}),
        }

    @staticmethod
    def _stem(word: str) -> str:
        for suffix in ("ization", "ation", "ments", "ment", "ingly", "edly", "ing", "ies", "ed", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                return word[:-len(suffix)] + ("y" if suffix == "ies" else "")
        return word

    def _similarity(self, left: Dict[str, Any], right: Dict[str, Any]) -> float:
        if left.get("normalized") == right.get("normalized"):
            return 1.0
        token = self._cosine(left.get("tokens", {}), right.get("tokens", {}))
        bigram = self._cosine(left.get("bigrams", {}), right.get("bigrams", {}))
        chars = self._cosine(left.get("chars", {}), right.get("chars", {}))
        entity = self._jaccard(left.get("entities", []), right.get("entities", []))
        tags = self._jaccard(left.get("tags", []), right.get("tags", []))
        score = 0.46 * token + 0.12 * bigram + 0.14 * chars + 0.08 * entity + 0.20 * tags
        if token >= 0.55 and (entity >= 0.25 or tags >= 0.25):
            score += 0.08
        return round(min(1.0, score), 4)

    @staticmethod
    def _cosine(left: Dict[str, float], right: Dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        overlap = set(left) & set(right)
        dot = sum(float(left[key]) * float(right[key]) for key in overlap)
        norm_left = math.sqrt(sum(float(value) ** 2 for value in left.values()))
        norm_right = math.sqrt(sum(float(value) ** 2 for value in right.values()))
        return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0

    @staticmethod
    def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
        first, second = set(left), set(right)
        return len(first & second) / len(first | second) if first and second else 0.0

    @staticmethod
    def _relationship(score: float) -> str:
        return "near-duplicate" if score >= 0.78 else "paraphrase" if score >= 0.42 else "related"

    def _match(self, record: Dict[str, Any], score: float, relationship: str) -> NarrativeMatch:
        return NarrativeMatch(
            intake_id=record["intake_id"], similarity=round(score, 4), relationship=relationship,
            platform=record["platform"], actor_id=record.get("actor_id"), region=record.get("region"),
            observed_at=_utc(record["observed_at"]), text_preview=self._preview(record["text"]),
        )

    def _observation(self, record: Dict[str, Any], similarity: Optional[float]) -> NarrativeObservation:
        return NarrativeObservation(
            intake_id=record["intake_id"], platform=record["platform"], actor_id=record.get("actor_id"),
            region=record.get("region"), observed_at=_utc(record["observed_at"]),
            classification=record["classification"], composite_score=record["composite_score"],
            text_preview=self._preview(record["text"]), similarity_to_previous=similarity,
        )

    @staticmethod
    def _preview(text: str, limit: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        return compact if len(compact) <= limit else compact[: limit - 1] + "…"

    @staticmethod
    def _cluster_id(component: Iterable[str]) -> str:
        digest = hashlib.sha1("|".join(sorted(component)).encode()).hexdigest()[:12]
        return f"narr-{digest}"

    def _cluster_label(self, records: Sequence[Dict[str, Any]]) -> str:
        tags = Counter(tag for record in records for tag in record.get("tags", []))
        if tags:
            return " / ".join(tag for tag, _ in tags.most_common(3))
        tokens = Counter(
            token for record in records for token, count in record.get("features", {}).get("tokens", {}).items()
            for _ in range(min(int(count), 3)) if len(token) > 3
        )
        return " · ".join(token for token, _ in tokens.most_common(4)) or "Unlabelled narrative"

    @staticmethod
    def _velocity(records: Sequence[Dict[str, Any]], now: datetime) -> tuple[float, float]:
        recent = sum(_utc(item["observed_at"]) >= now - timedelta(hours=2) for item in records)
        previous = sum(now - timedelta(hours=4) <= _utc(item["observed_at"]) < now - timedelta(hours=2) for item in records)
        return round(recent / 2, 3), round((recent - previous) / max(1, previous), 3)

    @staticmethod
    def _query_match(record: Dict[str, Any], query: Optional[str]) -> bool:
        if not query:
            return True
        needle = query.lower()
        haystack = " ".join([record.get("text", ""), record.get("region") or "", *record.get("tags", [])]).lower()
        return all(term in haystack for term in needle.split())

    @staticmethod
    def _timeline(records: Sequence[Dict[str, Any]], start: datetime, end: datetime) -> list[TimelineBucket]:
        total_hours = max(1, math.ceil((end - start).total_seconds() / 3600))
        bucket_hours = 1 if total_hours <= 48 else 6 if total_hours <= 168 else 24
        buckets: Dict[datetime, list[Dict[str, Any]]] = defaultdict(list)
        for record in records:
            observed = _utc(record["observed_at"])
            hour = (observed.hour // bucket_hours) * bucket_hours
            buckets[observed.replace(hour=hour, minute=0, second=0, microsecond=0)].append(record)
        return [
            TimelineBucket(
                start=key, posts=len(items),
                high_risk=sum(item["composite_score"] >= 0.7 for item in items),
            )
            for key, items in sorted(buckets.items())
        ]
