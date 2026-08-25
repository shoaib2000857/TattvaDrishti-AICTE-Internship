from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import networkx as nx

from ..schemas import (
    CommunitySnapshot,
    ContentIntake,
    CoordinationAlert,
    GNNCluster,
    GraphSummary,
    NarrativeMatch,
    PropagationChain,
    SIEMCorrelationPayload,
    ThreatIntelFeed,
)


class GraphIntelEngine:
    def __init__(self) -> None:
        self.graph = nx.Graph()

    def ingest(
        self,
        intake_id: str,
        intake: ContentIntake,
        classification: str,
        composite_score: float,
        similar_matches: Sequence[NarrativeMatch] = (),
        *,
        summarize: bool = True,
    ) -> Optional[GraphSummary]:
        platform = "unknown"
        if intake.metadata and intake.metadata.platform:
            platform = intake.metadata.platform

        content_node = f"content::{intake_id}"
        observed_at = (
            intake.metadata.observed_at
            if intake.metadata and intake.metadata.observed_at
            else datetime.utcnow()
        )
        self.graph.add_node(
            content_node,
            type="content",
            score=composite_score,
            classification=classification,
            ts=observed_at.isoformat(),
            platform=platform,
            source=intake.source,
            text_preview=" ".join(intake.text.split())[:220],
        )

        actor_id = (
            intake.metadata.actor_id
            if intake.metadata and intake.metadata.actor_id
            else f"actor::anon::{hash(intake.source) % 10000}"
        )
        self.graph.add_node(actor_id, type="actor")
        actor_record = self.graph.nodes[actor_id]
        history = actor_record.get("score_history", [])
        history.append(composite_score)
        actor_record["score_history"] = history[-20:]
        actor_record["avg_score"] = sum(actor_record["score_history"]) / len(actor_record["score_history"])
        platforms = set(actor_record.get("platforms", []))
        if platform:
            platforms.add(platform)
        actor_record["platforms"] = sorted(platforms)
        actor_record["last_seen"] = datetime.utcnow().isoformat()

        self.graph.add_edge(actor_id, content_node, relation="published")

        if intake.tags:
            for tag in intake.tags:
                tag_node = f"narrative::{tag}"
                self.graph.add_node(tag_node, type="narrative", tag=tag)
                self.graph.add_edge(content_node, tag_node, relation="targets")

        if intake.metadata and intake.metadata.region:
            region_node = f"region::{intake.metadata.region}"
            self.graph.add_node(region_node, type="region")
            self.graph.add_edge(actor_id, region_node, relation="origin")

        for match in similar_matches:
            peer = f"content::{match.intake_id}"
            if peer in self.graph:
                self.graph.add_edge(
                    content_node,
                    peer,
                    relation="semantically_similar",
                    weight=match.similarity,
                    relationship=match.relationship,
                )

        return self._summarise() if summarize else None

    def summary(self) -> GraphSummary:
        return self._summarise()

    def hydrate(
        self,
        records: Sequence[Dict[str, object]],
        edges: Sequence[Dict[str, object]],
    ) -> None:
        """Restore graph state from the persistent narrative evidence store."""
        self.graph.clear()
        for record in sorted(records, key=lambda item: str(item.get("observed_at", ""))):
            intake = ContentIntake(
                text=str(record.get("text") or "Historical evidence record unavailable."),
                source=str(record.get("source") or "unknown"),
                metadata={
                    "platform": str(record.get("platform") or "unknown"),
                    "actor_id": record.get("actor_id"),
                    "region": record.get("region"),
                    "observed_at": record.get("observed_at"),
                },
                tags=list(record.get("tags") or []),
            )
            self.ingest(
                str(record["intake_id"]),
                intake,
                str(record.get("classification") or "unknown"),
                float(record.get("composite_score") or 0.0),
                summarize=False,
            )
        for edge in edges:
            source = f"content::{edge['source']}"
            target = f"content::{edge['target']}"
            if source in self.graph and target in self.graph:
                self.graph.add_edge(
                    source,
                    target,
                    relation="semantically_similar",
                    weight=float(edge.get("similarity") or 0.0),
                    relationship=str(edge.get("relationship") or "related"),
                )

    def threat_intel_feed(self) -> ThreatIntelFeed:
        summary = self._summarise()
        indicator_pool = set(summary.high_risk_actors)
        for cluster in summary.gnn_clusters:
            indicator_pool.update(cluster.actors)
            indicator_pool.update(cluster.content)
            indicator_pool.update(f"narrative::{tag}" for tag in cluster.narratives)
        for alert in summary.coordination_alerts:
            indicator_pool.add(alert.actor)
            indicator_pool.update(alert.peer_actors)
        payload_fingerprint = hashlib.sha1(
            json.dumps(summary.dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()
        return ThreatIntelFeed(
            generated_at=datetime.utcnow(),
            graph_summary=summary,
            indicators=sorted(indicator_pool),
            dataset_fingerprint=payload_fingerprint,
        )

    def siem_payload(self) -> SIEMCorrelationPayload:
        summary = self._summarise()
        correlation_keys = sorted(
            {
                *(cluster.cluster_id for cluster in summary.gnn_clusters),
                *(alert.actor for alert in summary.coordination_alerts),
            }
        )
        return SIEMCorrelationPayload(
            generated_at=datetime.utcnow(),
            alerts=summary.coordination_alerts,
            propagation_chains=summary.propagation_chains,
            correlation_keys=correlation_keys,
            node_count=summary.node_count,
        )

    def _summarise(self) -> GraphSummary:
        node_count = self.graph.number_of_nodes()
        edge_count = self.graph.number_of_edges()
        gnn_projection = self._gnn_projection()
        high_risk = self._top_risk_actors(gnn_projection)
        communities = self._communities_snapshot(gnn_projection)
        gnn_clusters = self._gnn_clusters(gnn_projection)
        coordination_alerts = self._coordination_alerts(gnn_projection)
        propagation = self._propagation_chains(gnn_projection)

        return GraphSummary(
            node_count=node_count,
            edge_count=edge_count,
            high_risk_actors=high_risk,
            communities=communities,
            gnn_clusters=gnn_clusters,
            coordination_alerts=coordination_alerts,
            propagation_chains=propagation,
        )

    def _gnn_projection(self) -> Dict[str, List[float]]:
        if self.graph.number_of_nodes() == 0:
            return {}
        nodes = list(self.graph.nodes())
        features = {node: self._node_feature_vector(node) for node in nodes}
        own_weights = (0.4, 0.9, 0.3, 0.2, 1.1)
        neighbor_weights = (0.2, 0.6, 0.2, 0.2, 0.8)
        scores: List[float] = []
        for node in nodes:
            totals = [0.0] * 5
            denominator = 0.0
            for neighbor in self.graph.neighbors(node):
                weight = float(self.graph.edges[node, neighbor].get("weight", 1.0))
                denominator += weight
                for index, value in enumerate(features[neighbor]):
                    totals[index] += value * weight
            averages = [value / denominator for value in totals] if denominator else totals
            logit = 0.05
            logit += sum(a * b for a, b in zip(features[node], own_weights))
            logit += sum(a * b for a, b in zip(averages, neighbor_weights))
            scores.append(1.0 / (1.0 + math.exp(-logit)))
        return {"nodes": nodes, "scores": scores}

    def _node_feature_vector(self, node: str) -> List[float]:
        data = self.graph.nodes[node]
        node_type = data.get("type", "content")
        score = float(data.get("score", data.get("avg_score", 0.0)))
        class_score = {
            "high-risk": 0.9,
            "medium-risk": 0.6,
            "low-risk": 0.2,
        }.get(data.get("classification"), 0.4)
        platform_density = (
            min(1.0, len(data.get("platforms", [])) / 3)
            if node_type == "actor" else 0.0
        )
        return [
            float(node_type == "actor"),
            float(node_type == "content"),
            float(node_type == "narrative"),
            float(node_type == "region"),
            min(1.0, 0.7 * score + 0.3 * class_score + 0.2 * platform_density),
        ]

    def _top_risk_actors(self, gnn_projection: Dict[str, List[float]], limit: int = 5) -> List[str]:
        actors = [
            (node, data)
            for node, data in self.graph.nodes(data=True)
            if data.get("type") == "actor"
        ]
        score_lookup = dict(zip(gnn_projection.get("nodes", []), gnn_projection.get("scores", [])))
        scores: List[Tuple[str, float]] = []
        for actor, _ in actors:
            neighbor_scores = [
                self.graph.nodes[n].get("score", 0.0)
                for n in self.graph.neighbors(actor)
                if self.graph.nodes[n].get("type") == "content"
            ]
            if neighbor_scores:
                avg_neighbor = sum(neighbor_scores) / len(neighbor_scores)
                combined = 0.6 * avg_neighbor + 0.4 * score_lookup.get(actor, avg_neighbor)
                scores.append((actor, combined))
        scores.sort(key=lambda item: item[1], reverse=True)
        return [actor for actor, _ in scores[:limit]]

    def _communities_snapshot(
        self, gnn_projection: Dict[str, List[float]]
    ) -> List[CommunitySnapshot]:
        communities: List[CommunitySnapshot] = []
        score_lookup = dict(zip(gnn_projection.get("nodes", []), gnn_projection.get("scores", [])))
        for content_component in self._content_components():
            members = list(content_component | {
                neighbor
                for content in content_component
                for neighbor in self.graph.neighbors(content)
                if self.graph.nodes[neighbor].get("type") != "content"
            })
            content = [node for node in members if self.graph.nodes[node].get("type") == "content"]
            actors = [node for node in members if self.graph.nodes[node].get("type") == "actor"]
            narratives = [node for node in members if self.graph.nodes[node].get("type") == "narrative"]
            regions = [node for node in members if self.graph.nodes[node].get("type") == "region"]
            if not (content or actors or narratives):
                continue
            avg_score = (
                sum(score_lookup.get(node, 0.0) for node in members) / len(members)
                if members
                else 0.0
            )
            communities.append(
                CommunitySnapshot(
                    actors=actors,
                    content=content,
                    narratives=[node.split("::", 1)[1] for node in narratives],
                    regions=[node.split("::", 1)[1] for node in regions],
                    gnn_score=round(avg_score, 3),
                )
            )
        communities.sort(
            key=lambda item: (len(item.content), item.gnn_score),
            reverse=True,
        )
        return communities[:20]

    def _gnn_clusters(
        self, gnn_projection: Dict[str, List[float]], limit: int = 5
    ) -> List[GNNCluster]:
        if not gnn_projection:
            return []
        score_lookup = dict(zip(gnn_projection.get("nodes", []), gnn_projection.get("scores", [])))
        clusters: List[GNNCluster] = []
        for content_component in self._content_components():
            members = list(content_component | {
                neighbor
                for content in content_component
                for neighbor in self.graph.neighbors(content)
                if self.graph.nodes[neighbor].get("type") != "content"
            })
            if not members:
                continue
            avg_score = sum(score_lookup.get(node, 0.0) for node in members) / len(members)
            if avg_score < 0.35:
                continue
            actors = [node for node in members if self.graph.nodes[node].get("type") == "actor"]
            narratives = [
                self.graph.nodes[node].get("tag", node.split("::", 1)[-1])
                for node in members if self.graph.nodes[node].get("type") == "narrative"
            ]
            content = [node for node in members if self.graph.nodes[node].get("type") == "content"]
            cluster_digest = hashlib.sha1(
                "|".join(sorted(content)).encode("utf-8")
            ).hexdigest()[:10]
            clusters.append(
                GNNCluster(
                    cluster_id=f"cluster-{cluster_digest}",
                    score=round(avg_score, 3),
                    actors=actors[:10],
                    narratives=narratives[:10],
                    content=content[:10],
                )
            )
        clusters.sort(key=lambda cluster: cluster.score, reverse=True)
        return clusters[:limit]

    def _content_components(self) -> List[set[str]]:
        """Cluster evidence by semantic edges, not shared region or generic tags."""
        projection = nx.Graph()
        projection.add_nodes_from(
            node for node, data in self.graph.nodes(data=True)
            if data.get("type") == "content"
        )
        projection.add_edges_from(
            (source, target)
            for source, target, data in self.graph.edges(data=True)
            if data.get("relation") == "semantically_similar"
        )
        return [set(component) for component in nx.connected_components(projection)]

    def _coordination_alerts(
        self, gnn_projection: Dict[str, List[float]], limit: int = 10
    ) -> List[CoordinationAlert]:
        if not gnn_projection:
            return []
        score_lookup = dict(zip(gnn_projection.get("nodes", []), gnn_projection.get("scores", [])))
        alerts: List[CoordinationAlert] = []
        for actor, data in self.graph.nodes(data=True):
            if data.get("type") != "actor":
                continue
            content_neighbors = [
                neighbor
                for neighbor in self.graph.neighbors(actor)
                if self.graph.nodes[neighbor].get("type") == "content"
            ]
            related_content = set()
            for content in content_neighbors:
                for neighbor in self.graph.neighbors(content):
                    neighbor_type = self.graph.nodes[neighbor].get("type")
                    relation = self.graph.edges[content, neighbor].get("relation")
                    if neighbor_type == "content" and relation == "semantically_similar":
                        related_content.add(neighbor)
            peer_actors = sorted({
                peer
                for content in related_content
                for peer in self.graph.neighbors(content)
                if self.graph.nodes[peer].get("type") == "actor" and peer != actor
            })
            if not peer_actors:
                continue
            shared_tags = sorted(
                {
                    self.graph.nodes[tag].get("tag", tag.split("::", 1)[-1])
                    for content in content_neighbors
                    for tag in self.graph.neighbors(content)
                    if self.graph.nodes[tag].get("type") == "narrative"
                }
            )
            if not shared_tags:
                shared_tags = ["semantic paraphrase"]
            platforms = sorted(
                {
                    self.graph.nodes[content].get("platform", "unknown") or "unknown"
                    for content in [*content_neighbors, *related_content]
                }
            ) or ["unknown"]
            risk = max(
                score_lookup.get(actor, 0.0),
                max((score_lookup.get(peer, 0.0) for peer in peer_actors), default=0.0),
            )
            alerts.append(
                CoordinationAlert(
                    actor=actor,
                    peer_actors=peer_actors[:5],
                    shared_tags=shared_tags[:5],
                    platforms=platforms,
                    risk=round(risk, 3),
                )
            )
        alerts.sort(key=lambda alert: alert.risk, reverse=True)
        return alerts[:limit]

    def _propagation_chains(
        self, gnn_projection: Dict[str, List[float]], limit: int = 5
    ) -> List[PropagationChain]:
        if not gnn_projection:
            return []
        score_lookup = dict(zip(gnn_projection.get("nodes", []), gnn_projection.get("scores", [])))
        chains: List[PropagationChain] = []
        semantic_graph = nx.Graph()
        semantic_graph.add_nodes_from(
            node for node, data in self.graph.nodes(data=True)
            if data.get("type") == "content"
        )
        for source, target, data in self.graph.edges(data=True):
            if data.get("relation") == "semantically_similar":
                semantic_graph.add_edge(source, target, **data)

        for component in nx.connected_components(semantic_graph):
            if len(component) < 2:
                continue
            ordered = sorted(component, key=lambda node: self.graph.nodes[node].get("ts", ""))
            path: List[str] = []
            platforms: List[str] = []
            for content in ordered:
                actors = [
                    node for node in self.graph.neighbors(content)
                    if self.graph.nodes[node].get("type") == "actor"
                ]
                if actors:
                    path.append(actors[0])
                path.append(content)
                platform = self.graph.nodes[content].get("platform", "unknown") or "unknown"
                if platform not in platforms:
                    platforms.append(platform)
            weights = [
                float(data.get("weight", 0.0))
                for _, _, data in semantic_graph.subgraph(component).edges(data=True)
            ]
            likelihood = (
                sum(weights) / len(weights)
                if weights
                else sum(score_lookup.get(node, 0.0) for node in ordered) / len(ordered)
            )
            chains.append(
                PropagationChain(
                    path=path[:30],
                    likelihood=round(min(0.99, likelihood), 3),
                    platforms=platforms,
                )
            )
        chains.sort(key=lambda item: (len(item.platforms), item.likelihood), reverse=True)
        return chains[:limit]
