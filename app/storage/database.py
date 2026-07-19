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
