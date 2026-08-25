import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import get_settings


def _json_default(value: Any) -> str:
    """Serialize Pydantic URL types, datetimes, and other evidence metadata."""
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)


class Database:
    def __init__(self) -> None:
        settings = get_settings()
        self.path = settings.database_url.replace("sqlite:///", "")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _initialise(self) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    intake_id TEXT PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    composite_score REAL NOT NULL,
                    metadata_json TEXT,
                    breakdown_json TEXT,
                    provenance_json TEXT,
                    summary_text TEXT,
                    decision_reason TEXT,
                    created_at TEXT NOT NULL
                )
            """
            )
            cur.execute("PRAGMA table_info(cases)")
            columns = {row[1] for row in cur.fetchall()}
            if "summary_text" not in columns:
                cur.execute("ALTER TABLE cases ADD COLUMN summary_text TEXT")
            if "decision_reason" not in columns:
                cur.execute("ALTER TABLE cases ADD COLUMN decision_reason TEXT")
            if "batch_id" not in columns:
                cur.execute("ALTER TABLE cases ADD COLUMN batch_id TEXT")
            if "external_message_id" not in columns:
                cur.execute("ALTER TABLE cases ADD COLUMN external_message_id TEXT")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_cases_batch_id ON cases(batch_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_cases_external_message_id "
                "ON cases(external_message_id)"
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intake_id TEXT,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT,
                    created_at TEXT NOT NULL
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fingerprints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intake_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    normalized_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS secure_transfer_receipts (
                    envelope_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    source_node TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    ciphertext_sha256 TEXT NOT NULL,
                    received_at TEXT NOT NULL
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS secure_transfer_outbox (
                    envelope_id TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    intake_id TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS narrative_observations (
                    intake_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    actor_id TEXT,
                    region TEXT,
                    source TEXT,
                    tags_json TEXT,
                    observed_at TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    composite_score REAL NOT NULL,
                    feature_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS narrative_edges (
                    source_intake_id TEXT NOT NULL,
                    target_intake_id TEXT NOT NULL,
                    similarity REAL NOT NULL,
                    relationship TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (source_intake_id, target_intake_id)
                )
            """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_narrative_observed_at "
                "ON narrative_observations(observed_at)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_narrative_platform "
                "ON narrative_observations(platform)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_narrative_edge_source "
                "ON narrative_edges(source_intake_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_narrative_edge_target "
                "ON narrative_edges(target_intake_id)"
            )

    @contextmanager
    def _cursor(self):
        conn = sqlite3.connect(self.path, timeout=30.0)
        try:
            conn.execute("PRAGMA busy_timeout=30000")
            cur = conn.cursor()
            yield cur
            conn.commit()
        finally:
            conn.close()

    def save_case(
        self,
        intake_id: str,
        raw_text: str,
        classification: str,
        composite_score: float,
        metadata: Dict[str, Any],
        breakdown: Dict[str, Any],
        provenance: Dict[str, Any],
        summary: Optional[str] = None,
        decision_reason: Optional[str] = None,
        batch_id: Optional[str] = None,
        external_message_id: Optional[str] = None,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO cases (
                    intake_id,
                    raw_text,
                    classification,
                    composite_score,
                    metadata_json,
                    breakdown_json,
                    provenance_json,
                    summary_text,
                    decision_reason,
                    batch_id,
                    external_message_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    intake_id,
                    raw_text,
                    classification,
                    composite_score,
                    json.dumps(metadata, default=_json_default),
                    json.dumps(breakdown, default=_json_default),
                    json.dumps(provenance, default=_json_default),
                    summary,
                    decision_reason,
                    batch_id,
                    external_message_id,
                    datetime.utcnow().isoformat(),
                ),
            )

    def _normalize_text(self, text: str) -> str:
        # simple normalization for fuzzy match: lowercase and collapse whitespace
        return "".join(text.lower().split())

    def store_fingerprint(self, intake_id: str, text: str, content_hash: str) -> None:
        normalized_hash = hashlib.sha256(self._normalize_text(text).encode("utf-8")).hexdigest()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO fingerprints (intake_id, content_hash, normalized_hash, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (intake_id, content_hash, normalized_hash, datetime.utcnow().isoformat()),
            )

    def check_fingerprint(self, text: str) -> list[Dict[str, Any]]:
        normalized_hash = hashlib.sha256(self._normalize_text(text).encode("utf-8")).hexdigest()
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT intake_id, content_hash, normalized_hash, created_at
                FROM fingerprints
                WHERE normalized_hash = ? OR content_hash = ?
            """,
                (normalized_hash, normalized_hash),
            )
            rows = cur.fetchall() or []
            return [
                {
                    "intake_id": r[0],
                    "content_hash": r[1],
                    "normalized_hash": r[2],
                    "created_at": r[3],
                }
                for r in rows
            ]

    def fetch_case(self, intake_id: str) -> Optional[Dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT
                    raw_text,
                    classification,
                    composite_score,
                    metadata_json,
                    breakdown_json,
                    provenance_json,
                    summary_text,
                    decision_reason,
                    batch_id,
                    external_message_id,
                    created_at
                FROM cases WHERE intake_id=?
            """,
                (intake_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            metadata_json = json.loads(row[3]) if row[3] else {}
            breakdown = json.loads(row[4]) if row[4] else {}
            provenance = json.loads(row[5]) if row[5] else {}
            return {
                "raw_text": row[0],
                "classification": row[1],
                "composite_score": row[2],
                "metadata": metadata_json,
                "breakdown": breakdown,
                "provenance": provenance,
                "summary": row[6],
                "decision_reason": row[7],
                "batch_id": row[8],
                "external_message_id": row[9],
                "created_at": row[10],
            }

    def fetch_cases(self, limit: int = 5000) -> list[Dict[str, Any]]:
        """Return stored cases in collection order for narrative backfill."""
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT intake_id, raw_text, classification, composite_score,
                       metadata_json, created_at
                FROM cases
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            return [
                {
                    "intake_id": row[0],
                    "raw_text": row[1],
                    "classification": row[2],
                    "composite_score": row[3],
                    "metadata": json.loads(row[4] or "{}"),
                    "created_at": row[5],
                }
                for row in cur.fetchall()
            ]

    def log_action(self, intake_id: str, action: str, actor: str, payload: Dict[str, Any]):
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (intake_id, action, actor, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    intake_id,
                    action,
                    actor,
                    json.dumps(payload, default=_json_default),
                    datetime.utcnow().isoformat(),
                ),
            )

    def record_secure_transfer(
        self,
        *,
        envelope_id: str,
        package_id: str,
        source_node: str,
        destination: str,
        ciphertext_sha256: str,
    ) -> bool:
        """Persist a replay-resistant receipt; return False for a duplicate."""
        with self._cursor() as cur:
            cur.execute(
                "SELECT 1 FROM secure_transfer_receipts WHERE envelope_id=?",
                (envelope_id,),
            )
            if cur.fetchone():
                return False
            cur.execute(
                """
                INSERT INTO secure_transfer_receipts (
                    envelope_id, package_id, source_node, destination,
                    ciphertext_sha256, received_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope_id,
                    package_id,
                    source_node,
                    destination,
                    ciphertext_sha256,
                    datetime.utcnow().isoformat(),
                ),
            )
            return True

    def save_secure_outbox(
        self,
        *,
        envelope_id: str,
        package_id: str,
        intake_id: str,
        destination: str,
        envelope: Dict[str, Any],
        status: str = "prepared",
    ) -> None:
        timestamp = datetime.utcnow().isoformat()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO secure_transfer_outbox (
                    envelope_id, package_id, intake_id, destination,
                    envelope_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope_id,
                    package_id,
                    intake_id,
                    destination,
                    json.dumps(envelope, default=_json_default),
                    status,
                    timestamp,
                    timestamp,
                ),
            )

    def update_secure_outbox_status(self, envelope_id: str, status: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE secure_transfer_outbox
                SET status=?, updated_at=?
                WHERE envelope_id=?
                """,
                (status, datetime.utcnow().isoformat(), envelope_id),
            )

    def save_narrative_observation(self, record: Dict[str, Any]) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO narrative_observations (
                    intake_id, text, platform, actor_id, region, source,
                    tags_json, observed_at, classification, composite_score,
                    feature_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["intake_id"], record["text"], record["platform"],
                    record.get("actor_id"), record.get("region"), record.get("source"),
                    json.dumps(record.get("tags", [])), record["observed_at"],
                    record["classification"], record["composite_score"],
                    json.dumps(record["features"]), datetime.utcnow().isoformat(),
                ),
            )

    def save_narrative_edge(
        self, source_id: str, target_id: str, similarity: float, relationship: str
    ) -> None:
        source_id, target_id = sorted((source_id, target_id))
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO narrative_edges (
                    source_intake_id, target_intake_id, similarity,
                    relationship, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (source_id, target_id, similarity, relationship, datetime.utcnow().isoformat()),
            )

    def fetch_narrative_observations(self, limit: int = 5000) -> list[Dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT intake_id, text, platform, actor_id, region, source,
                       tags_json, observed_at, classification, composite_score,
                       feature_json
                FROM narrative_observations
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            return [
                {
                    "intake_id": row[0], "text": row[1], "platform": row[2],
                    "actor_id": row[3], "region": row[4], "source": row[5],
                    "tags": json.loads(row[6] or "[]"), "observed_at": row[7],
                    "classification": row[8], "composite_score": row[9],
                    "features": json.loads(row[10] or "{}"),
                }
                for row in cur.fetchall()
            ]

    def fetch_narrative_edges(self, intake_id: Optional[str] = None) -> list[Dict[str, Any]]:
        with self._cursor() as cur:
            query = (
                "SELECT source_intake_id, target_intake_id, similarity, relationship "
                "FROM narrative_edges"
            )
            if intake_id:
                query += " WHERE source_intake_id=? OR target_intake_id=?"
                cur.execute(query, (intake_id, intake_id))
            else:
                cur.execute(query)
            return [
                {"source": row[0], "target": row[1], "similarity": row[2], "relationship": row[3]}
                for row in cur.fetchall()
            ]
