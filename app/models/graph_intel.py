from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import networkx as nx

try:  # pragma: no cover - torch is optional during docs build
    import torch
except Exception:  # noqa: BLE001
    torch = None  # type: ignore

from ..schemas import (
    CommunitySnapshot,
    ContentIntake,
    CoordinationAlert,
    GNNCluster,
    GraphSummary,
    PropagationChain,
    SIEMCorrelationPayload,
    ThreatIntelFeed,
)


class GraphIntelEngine:
    def __init__(self) -> None:
        self.graph = nx.Graph()
        if torch:
            self._feature_weights = torch.tensor([0.4, 0.9, 0.3, 0.2, 1.1], dtype=torch.float32)
            self._neighbor_weights = torch.tensor([0.2, 0.6, 0.2, 0.2, 0.8], dtype=torch.float32)
            self._gnn_bias = torch.tensor(0.05, dtype=torch.float32)
        else:  # pragma: no cover - fallback when torch missing
            self._feature_weights = None
            self._neighbor_weights = None
            self._gnn_bias = None

    def ingest(
        self,
        intake_id: str,
        intake: ContentIntake,
        classification: str,
        composite_score: float,
        *,
        summarize: bool = True,
    ) -> Optional[GraphSummary]:
        platform = "unknown"
        if intake.metadata and intake.metadata.platform:
            platform = intake.metadata.platform

        content_node = f"content::{intake_id}"
        self.graph.add_node(
            content_node,
            type="content",
            score=composite_score,
            classification=classification,
            ts=datetime.utcnow().isoformat(),
            platform=platform,
            source=intake.source,
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

        return self._summarise() if summarize else None

    def summary(self) -> GraphSummary:
        return self._summarise()

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
        if not torch or self.graph.number_of_nodes() == 0:
            return {}
        nodes = list(self.graph.nodes())
        feature_matrix = self._build_feature_matrix(nodes)
        adjacency = self._build_adjacency(nodes)
        degrees = adjacency.sum(dim=1, keepdim=True).clamp(min=1.0)
        neighbor_features = adjacency @ feature_matrix / degrees
        base_scores = (feature_matrix * self._feature_weights).sum(dim=1)
        neighbor_effect = (neighbor_features * self._neighbor_weights).sum(dim=1)
        context_features = adjacency @ neighbor_features / degrees
        context_effect = 0.5 * (context_features * self._neighbor_weights).sum(dim=1)
        logits = base_scores + neighbor_effect + context_effect + self._gnn_bias
        scores = torch.sigmoid(logits).tolist()
        return {"nodes": nodes, "scores": scores}

    def _build_feature_matrix(self, nodes: List[str]):
        rows: List[List[float]] = []
        for node in nodes:
            data = self.graph.nodes[node]
            node_type = data.get("type", "content")
            score = float(data.get("score", data.get("avg_score", 0.0)))
            classification = data.get("classification")
            class_score = {
                "high-risk": 0.9,
                "medium-risk": 0.6,
                "low-risk": 0.2,
            }.get(classification, 0.4)
            platform_density = min(1.0, len(data.get("platforms", [])) / 3) if node_type == "actor" else 0.0
            region_flag = 1.0 if node_type == "region" else 0.0
            rows.append(
                [
                    1.0 if node_type == "actor" else 0.0,
                    1.0 if node_type == "content" else 0.0,
                    1.0 if node_type == "narrative" else 0.0,
                    region_flag,
                    min(1.0, 0.7 * score + 0.3 * class_score + 0.2 * platform_density),
                ]
            )
        return torch.tensor(rows, dtype=torch.float32)

    def _build_adjacency(self, nodes: List[str]):
        adjacency = torch.zeros((len(nodes), len(nodes)), dtype=torch.float32)
        index_lookup = {node: idx for idx, node in enumerate(nodes)}
        for source, target in self.graph.edges():
            i = index_lookup[source]
            j = index_lookup[target]
            adjacency[i, j] = 1.0
            adjacency[j, i] = 1.0
        return adjacency

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
        for component in nx.connected_components(self.graph):
            members = list(component)
            content = [node for node in members if node.startswith("content::")]
            actors = [node for node in members if node.startswith("actor::")]
            narratives = [node for node in members if node.startswith("narrative::")]
            regions = [node for node in members if node.startswith("region::")]
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
        return communities

    def _gnn_clusters(
        self, gnn_projection: Dict[str, List[float]], limit: int = 5
    ) -> List[GNNCluster]:
        if not gnn_projection:
            return []
        score_lookup = dict(zip(gnn_projection.get("nodes", []), gnn_projection.get("scores", [])))
        clusters: List[GNNCluster] = []
        for idx, component in enumerate(nx.connected_components(self.graph), start=1):
            members = list(component)
            if not members:
                continue
            avg_score = sum(score_lookup.get(node, 0.0) for node in members) / len(members)
            if avg_score < 0.35:
                continue
            actors = [node for node in members if node.startswith("actor::")]
            narratives = [node.split("::", 1)[1] for node in members if node.startswith("narrative::")]
            content = [node for node in members if node.startswith("content::")]
            clusters.append(
                GNNCluster(
                    cluster_id=f"cluster-{idx}",
                    score=round(avg_score, 3),
                    actors=actors[:10],
                    narratives=narratives[:10],
                    content=content[:10],
                )
            )
        clusters.sort(key=lambda cluster: cluster.score, reverse=True)
        return clusters[:limit]

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
            peer_actors = sorted(
                {
                    peer
                    for content in content_neighbors
                    for peer in self.graph.neighbors(content)
                    if self.graph.nodes[peer].get("type") == "actor" and peer != actor
                }
            )
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
                continue
            platforms = sorted(
                {
                    self.graph.nodes[content].get("platform", "unknown") or "unknown"
                    for content in content_neighbors
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
        narrative_nodes = [node for node, data in self.graph.nodes(data=True) if data.get("type") == "narrative"]
        for narrative in narrative_nodes:
            actors = [
                neighbor
                for neighbor in self.graph.neighbors(narrative)
                if self.graph.nodes[neighbor].get("type") == "actor"
            ]
            contents = [
                neighbor
                for neighbor in self.graph.neighbors(narrative)
                if self.graph.nodes[neighbor].get("type") == "content"
            ]
            if len(actors) < 2 or not contents:
                continue
            ranked_actors = sorted(actors, key=lambda node: score_lookup.get(node, 0.0), reverse=True)[:2]
            for content in contents[:2]:
                path = [ranked_actors[0], content, narrative, ranked_actors[-1]]
                platforms = sorted({self.graph.nodes[content].get("platform", "unknown") or "unknown"})
                likelihood = (
                    score_lookup.get(content, 0.0)
                    + score_lookup.get(narrative, 0.0)
                    + sum(score_lookup.get(actor, 0.0) for actor in ranked_actors)
                ) / max(1, 2 + len(ranked_actors))
                chains.append(
                    PropagationChain(
                        path=path,
                        likelihood=round(min(0.99, likelihood), 3),
                        platforms=platforms,
                    )
                )
                if len(chains) >= limit:
                    return chains
        return chains
