from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceMetadata(BaseModel):
    platform: str = "unspecified"
    region: Optional[str] = None
    actor_id: Optional[str] = None
    related_urls: Optional[List[HttpUrl]] = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    observed_at: Optional[datetime] = None
    source_system: Optional[str] = None
    collection_id: Optional[str] = None
    classification_marking: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ContentIntake(BaseModel):
    text: str = Field(..., min_length=20, max_length=20000)
    language: str = Field("en", min_length=2, max_length=5)
    source: str = Field("unknown")
    metadata: Optional[SourceMetadata] = None
    tags: Optional[List[str]] = None


class BatchDefaults(BaseModel):
    """Values inherited by messages that omit the corresponding field."""

    language: str = Field("en", min_length=2, max_length=5)
    source: str = "unknown"
    metadata: Optional[SourceMetadata] = None
    tags: List[str] = Field(default_factory=list)


class BatchMessage(BaseModel):
    """Portable message record used by JSON envelopes and JSON Lines files."""

    message_id: str = Field(..., min_length=1, max_length=256)
    text: str = Field(..., min_length=20, max_length=20000)
    conversation_id: Optional[str] = Field(None, max_length=256)
    observed_at: Optional[datetime] = None
    language: Optional[str] = Field(None, min_length=2, max_length=5)
    source: Optional[str] = None
    metadata: Optional[SourceMetadata] = None
    tags: Optional[List[str]] = None


class BatchIntakeEnvelope(BaseModel):
    """Versioned, self-describing batch interchange document."""

    schema_version: Literal["1.0"] = "1.0"
    batch_id: Optional[str] = Field(None, min_length=1, max_length=256)
    source_system: str = Field(..., min_length=1, max_length=256)
    collection_id: Optional[str] = Field(None, max_length=256)
    classification_marking: Optional[str] = Field(None, max_length=256)
    defaults: BatchDefaults = Field(default_factory=BatchDefaults)
    messages: List[BatchMessage]


class BatchItemError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    line_number: Optional[int] = None


class BatchItemResult(BaseModel):
    index: int
    message_id: Optional[str] = None
    status: Literal["success", "error"]
    result: Optional["DetectionResult"] = None
    errors: List[BatchItemError] = Field(default_factory=list)


class BatchDetectionResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    batch_id: str
    source_system: str
    classification_marking: Optional[str] = None
    accepted_at: datetime
    completed_at: datetime
    duration_ms: int
    total: int
    succeeded: int
    failed: int
    items: List[BatchItemResult]


class DetectionBreakdown(BaseModel):
    linguistic_score: float
    behavioral_score: float
    ai_probability: Optional[float] = None
    model_family: Optional[str] = None
    model_family_confidence: Optional[float] = None
    model_family_probabilities: Optional[Dict[str, float]] = None
    ollama_risk: Optional[float] = None
    ollama_analysis: Optional[Dict[str, Any]] = None
    stylometric_anomalies: Dict[str, float]
    heuristics: List[str]


class ProvenancePayload(BaseModel):
    watermark_present: bool
    watermark_hash: Optional[str] = None
    signature_valid: bool
    validation_notes: List[str]
    content_hash: str


class GNNCluster(BaseModel):
    cluster_id: str
    score: float
    actors: List[str] = Field(default_factory=list)
    narratives: List[str] = Field(default_factory=list)
    content: List[str] = Field(default_factory=list)


class CoordinationAlert(BaseModel):
    actor: str
    peer_actors: List[str] = Field(default_factory=list)
    shared_tags: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    risk: float


class PropagationChain(BaseModel):
    path: List[str] = Field(default_factory=list)
    likelihood: float
    platforms: List[str] = Field(default_factory=list)


class NarrativeMatch(BaseModel):
    intake_id: str
    similarity: float
    relationship: Literal["near-duplicate", "paraphrase", "related"]
    platform: str
    actor_id: Optional[str] = None
    region: Optional[str] = None
    observed_at: datetime
    text_preview: str


class NarrativeObservation(BaseModel):
    intake_id: str
    platform: str
    actor_id: Optional[str] = None
    region: Optional[str] = None
    observed_at: datetime
    classification: str
    composite_score: float
    text_preview: str
    similarity_to_previous: Optional[float] = None


class OriginAssessment(BaseModel):
    intake_id: str
    platform: str
    actor_id: Optional[str] = None
    region: Optional[str] = None
    observed_at: datetime
    confidence: float
    basis: List[str] = Field(default_factory=list)
    caveat: str = "Earliest observation in collected evidence; not proof of authorship."


class NarrativeTrace(BaseModel):
    narrative_id: str
    label: str
    query_intake_id: str
    origin: OriginAssessment
    platforms: List[str]
    actors: List[str]
    regions: List[str]
    observations: List[NarrativeObservation]
    matches: List[NarrativeMatch]
    first_seen: datetime
    last_seen: datetime
    velocity_per_hour: float
    acceleration: float


class TimelineBucket(BaseModel):
    start: datetime
    posts: int
    high_risk: int


class Hotspot(BaseModel):
    region: str
    posts: int
    average_risk: float


class WarRoomNarrative(BaseModel):
    narrative_id: str
    label: str
    posts: int
    platforms: List[str]
    actors: int
    average_risk: float
    velocity_per_hour: float
    acceleration: float
    status: Literal["stable", "emerging", "accelerating"]
    first_seen: datetime
    last_seen: datetime


class WarRoomSnapshot(BaseModel):
    title: str
    generated_at: datetime
    window_hours: int
    posts_analyzed: int
    major_narratives: int
    emerging_clusters: int
    high_priority_accounts: int
    accelerating_narratives: int
    narratives: List[WarRoomNarrative]
    hotspots: List[Hotspot]
    timeline: List[TimelineBucket]
    platforms: Dict[str, int]


class CopilotRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    intake_id: Optional[str] = None
    narrative_id: Optional[str] = None
    window_hours: int = Field(24, ge=1, le=720)


class EvidenceCitation(BaseModel):
    evidence_id: str
    description: str
    observed_at: Optional[datetime] = None


class CopilotResponse(BaseModel):
    answer: str
    citations: List[EvidenceCitation] = Field(default_factory=list)
    scope: str
    grounded: bool = True
    limitations: List[str] = Field(default_factory=list)


class CommunitySnapshot(BaseModel):
    actors: List[str] = Field(default_factory=list)
    content: List[str] = Field(default_factory=list)
    narratives: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    gnn_score: float = 0.0


class GraphSummary(BaseModel):
    node_count: int
    edge_count: int
    high_risk_actors: List[str]
    communities: List[CommunitySnapshot]
    gnn_clusters: List[GNNCluster] = Field(default_factory=list)
    coordination_alerts: List[CoordinationAlert] = Field(default_factory=list)
    propagation_chains: List[PropagationChain] = Field(default_factory=list)


class DetectionResult(BaseModel):
    intake_id: str
    submitted_at: datetime
    composite_score: float
    classification: str
    breakdown: DetectionBreakdown
    provenance: ProvenancePayload
    graph_summary: GraphSummary
    summary: Optional[str] = None
    findings: Optional[List[str]] = None
    decision_reason: Optional[str] = None


class ThreatIntelFeed(BaseModel):
    generated_at: datetime
    graph_summary: GraphSummary
    indicators: List[str]
    dataset_fingerprint: str


class SIEMCorrelationPayload(BaseModel):
    generated_at: datetime
    alerts: List[CoordinationAlert]
    propagation_chains: List[PropagationChain]
    correlation_keys: List[str]
    node_count: int


class SharingRequest(BaseModel):
    intake_id: str
    destination: str
    justification: str
    include_personal_data: bool = False
    transfer_mode: Literal["encrypted", "blockchain"] = "encrypted"


class HopTrace(BaseModel):
    id: str
    name: str
    city: str
    coords: List[float]
    ip: str
    provider: str
    latency: int
    note: Optional[str] = None


class SharingPackage(BaseModel):
    package_id: str
    created_at: datetime
    destination: str
    policy_tags: List[str]
    payload: Dict[str, str]
    signature: str
    hop_trace: Optional[List[HopTrace]] = None
    risk_level: str
    composite_score: float
    transfer_mode: Literal["encrypted", "blockchain"] = "encrypted"
    transfer_status: str = "prepared"
    transport_security: str = "AES-256-GCM"
    security: Dict[str, Any] = Field(default_factory=dict)


class SecureTransferEnvelope(BaseModel):
    """Opaque, authenticated envelope exchanged between partner nodes."""

    version: Literal["1.0"] = "1.0"
    envelope_id: str
    package_id: str
    source_node: str
    destination: str
    created_at: datetime
    expires_at: datetime
    algorithm: Literal["AES-256-GCM"] = "AES-256-GCM"
    key_id: str
    nonce: str
    aad: str
    ciphertext: str
    ciphertext_sha256: str
    signing_public_key: str
    signature: str


class SecureTransferReceipt(BaseModel):
    envelope_id: str
    package_id: str
    status: Literal["accepted", "duplicate"]
    received_at: datetime
    receiving_node: str
    ciphertext_sha256: str
