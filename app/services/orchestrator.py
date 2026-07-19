import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

import httpx

from ..models.detection import DetectorEngine
from ..models.graph_intel import GraphIntelEngine
from ..models.sharing import SharingEngine
from ..models.watermark import WatermarkEngine
from ..schemas import ContentIntake, DetectionResult, SharingPackage, SharingRequest
from ..storage.database import Database

try:
    from ..federated.manager import LedgerManager
    from ..federated.node import Node
    from ..federated.ledger import Block
    from ..federated.crypto import encrypt_data
    FEDERATED_ENABLED = True
except ImportError:
    FEDERATED_ENABLED = False


class AnalysisOrchestrator:
    def __init__(self) -> None:
        self.detector = DetectorEngine()
        self.watermark = WatermarkEngine()
        self.graph = GraphIntelEngine()
        self.sharing = SharingEngine()
        self.db = Database()
        self._event_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=200)
        # NetworkX mutation and SQLite writes are ordered. Expensive detector
        # stages run before this lock and therefore still benefit from batching.
        self._state_lock = threading.RLock()
        self._pipeline_executor = ThreadPoolExecutor(
            max_workers=max(2, self.detector.settings.batch_parallelism),
            thread_name_prefix="analysis-pipeline",
        )
        
        # Initialize federated ledger if available
        if FEDERATED_ENABLED:
            try:
                self.ledger = LedgerManager()
                self.node = Node()
            except Exception:
                self.ledger = None
                self.node = None
        else:
            self.ledger = None
            self.node = None

    async def process_intake(self, intake: ContentIntake) -> DetectionResult:
        return await self._await_pipeline(self._process_sync, intake)

    async def process_batch(
        self,
        records: Sequence[Tuple[str, ContentIntake]],
        *,
        batch_id: str,
        actor: str = "system",
    ) -> List[Tuple[Optional[DetectionResult], Optional[str]]]:
        """Analyze validated records as one model batch and persist in order."""
        return await self._await_pipeline(
            self._process_batch_sync,
            records,
            batch_id,
            actor,
        )

    async def _await_pipeline(self, function, *args):
        """Await dedicated worker work without depending on AnyIO's global pool."""
        future = self._pipeline_executor.submit(function, *args)
        while not future.done():
            await asyncio.sleep(0.01)
        return future.result()

    def _process_sync(self, intake: ContentIntake) -> DetectionResult:
        composite_score, classification, breakdown = self.detector.detect(intake)
        return self._complete_intake(
            intake,
            composite_score=composite_score,
            classification=classification,
            breakdown=breakdown,
        )

    def _process_batch_sync(
        self,
        records: Sequence[Tuple[str, ContentIntake]],
        batch_id: str,
        actor: str,
    ) -> List[Tuple[Optional[DetectionResult], Optional[str]]]:
        if not records:
            return []
        settings = self.detector.settings
        try:
            detections = self.detector.detect_batch(
                [intake for _, intake in records],
                ai_batch_size=settings.batch_ai_model_size,
                parallelism=settings.batch_parallelism,
                ollama_parallelism=settings.batch_ollama_parallelism,
            )
        except Exception as error:  # one infrastructure failure affects this model batch
            message = f"Detection batch failed: {type(error).__name__}: {error}"
            return [(None, message) for _ in records]

        outcomes: List[Tuple[Optional[DetectionResult], Optional[str]]] = []
        for (message_id, intake), detection in zip(records, detections):
            composite_score, classification, breakdown = detection
            try:
                result = self._complete_intake(
                    intake,
                    composite_score=composite_score,
                    classification=classification,
                    breakdown=breakdown,
                    batch_id=batch_id,
                    external_message_id=message_id,
                    actor=actor,
                    summarize_graph=False,
                )
                outcomes.append((result, None))
            except Exception as error:
                outcomes.append(
                    (None, f"Case persistence failed: {type(error).__name__}: {error}")
                )
        if len(outcomes) < len(records):
            outcomes.extend(
                (None, "Detection batch returned no result for this record.")
                for _ in range(len(records) - len(outcomes))
            )
        successful_results = [result for result, _ in outcomes if result is not None]
        if successful_results:
            # Summarising the growing GNN after every record is quadratic work
            # repeated N times. Batch ingestion mutates the graph in order and
            # computes one consistent post-batch snapshot for every result.
            with self._state_lock:
                batch_graph_summary = self.graph.summary()
            for result in successful_results:
                result.graph_summary = batch_graph_summary
        return outcomes

    def _complete_intake(
        self,
        intake: ContentIntake,
        *,
        composite_score: float,
        classification: str,
        breakdown,
        batch_id: Optional[str] = None,
        external_message_id: Optional[str] = None,
        actor: str = "system",
        summarize_graph: bool = True,
    ) -> DetectionResult:
        intake_id = str(uuid4())
        submitted_at = datetime.utcnow()
        provenance = self.watermark.verify(intake.text)
        summary_text = self._generate_summary(intake, classification, composite_score, breakdown)
        decision_reason = self._build_decision_reason(classification, composite_score, breakdown)
        with self._state_lock:
            graph_summary = self.graph.ingest(
                intake_id,
                intake,
                classification,
                composite_score,
                summarize=summarize_graph,
            )
            self.db.save_case(
                intake_id=intake_id,
                raw_text=intake.text,
                classification=classification,
                composite_score=composite_score,
                metadata=intake.dict().get("metadata", {}) or {},
                breakdown=breakdown.dict(),
                provenance=provenance.dict(),
                summary=summary_text,
                decision_reason=decision_reason,
                batch_id=batch_id,
                external_message_id=external_message_id,
            )
            audit_payload = {
                "score": composite_score,
                "classification": classification,
            }
            if batch_id:
                audit_payload["batch_id"] = batch_id
            if external_message_id:
                audit_payload["external_message_id"] = external_message_id
            self.db.log_action(
                intake_id=intake_id,
                action="analysis_completed",
                actor=actor,
                payload=audit_payload,
            )

            # Store fingerprint for post-hoc verification
            try:
                self.db.store_fingerprint(intake_id, intake.text, provenance.content_hash)
            except Exception:
                # non-fatal; continue
                pass

        if graph_summary is None:
            # Replaced with one post-batch snapshot by _process_batch_sync.
            graph_summary = self.graph.summary() if summarize_graph else {
                "node_count": 0,
                "edge_count": 0,
                "high_risk_actors": [],
                "communities": [],
            }

        result = DetectionResult(
            intake_id=intake_id,
            submitted_at=submitted_at,
            composite_score=composite_score,
            classification=classification,
            breakdown=breakdown,
            provenance=provenance,
            graph_summary=graph_summary,
            summary=summary_text,
            findings=breakdown.heuristics[:5] if breakdown.heuristics else None,
            decision_reason=decision_reason,
        )

        self._emit_event(
            {
                "type": "analysis_completed",
                "intake_id": intake_id,
                "score": composite_score,
                "classification": classification,
                "submitted_at": submitted_at.isoformat(),
                "batch_id": batch_id,
                "external_message_id": external_message_id,
            }
        )
        return result

    async def stream_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            event = await self._event_queue.get()
            yield event

    def check_fingerprint(self, text: str) -> list[Dict[str, Any]]:
        return self.db.check_fingerprint(text)

    async def _fetch_case_from_main_api(self, intake_id: str) -> Optional[Dict[str, Any]]:
        """Fetch case data from main API if not found locally (for federated nodes)."""
        main_api_url = os.getenv("MAIN_API_URL", "http://localhost:8000")
        # Don't fetch from self
        if main_api_url == os.getenv("NODE_URL"):
            return None
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{main_api_url}/api/v1/cases/{intake_id}")
                if response.status_code == 200:
                    data = response.json()
                    # Convert DetectionResult to the format expected by build_sharing_package
                    return {
                        "classification": data.get("classification"),
                        "composite_score": data.get("composite_score"),
                        "created_at": data.get("submitted_at"),
                        "metadata": data.get("metadata", {}),
                    }
        except Exception as e:
            print(f"Failed to fetch case from main API: {e}")
        return None

    async def build_sharing_package(self, request: SharingRequest) -> SharingPackage:
        record = self.db.fetch_case(request.intake_id)
        
        # If not found locally, try fetching from main API (for federated nodes)
        if not record:
            record = await self._fetch_case_from_main_api(request.intake_id)
        
        if not record:
            raise ValueError("Unknown intake reference.")
        payload = {
            "intake_id": request.intake_id,
            "classification": record["classification"],
            "composite_score": record["composite_score"],
            "created_at": record["created_at"],
        }
        metadata = record["metadata"]
        if not request.include_personal_data and isinstance(metadata, dict):
            metadata = {k: v for k, v in metadata.items() if k not in {"actor_id", "user_id"}}
        payload["metadata"] = metadata
        policy_tags = self._determine_policy(request)
        
        # Extract risk information
        classification = record.get("classification", "low-risk")
        composite_score = record.get("composite_score", 0.0)
        
        package = self.sharing.create_package(
            intake_id=request.intake_id,
            destination=request.destination,
            payload=payload,
            policy_tags=policy_tags,
            risk_level=classification,
            composite_score=composite_score,
        )
        self.db.log_action(
            intake_id=request.intake_id,
            action="package_generated",
            actor="system",
            payload={"destination": request.destination, "policy": policy_tags},
        )
        
        # Publish to federated blockchain if enabled
        if self.ledger and self.node:
            try:
                # Map destination to node URL (hardcoded to match NODE_URLS in frontend)
                destination_map = {
                    "USA": "http://localhost:8001",
                    "EU": "http://localhost:8002",
                    "IN": "http://localhost:8003",
                    "AUS": "http://localhost:8004",
                }
                
                destination_url = destination_map.get(request.destination)
                
                if destination_url:
                    # Get the chain from the destination node to append the block there
                    try:
                        import requests
                        
                        # Fetch destination node's chain
                        chain_response = requests.get(f"{destination_url}/api/v1/federated/chain", timeout=5.0)
                        if chain_response.status_code == 200:
                            dest_chain_data = chain_response.json()
                            dest_chain = dest_chain_data.get("chain", [])
                            
                            # Create block with proper index for destination node
                            prev_hash = dest_chain[-1]["hash"] if dest_chain else "0"
                            block_index = len(dest_chain)
                            
                            federated_payload = {
                                "type": "intelligence_sharing",
                                "package_id": package.package_id,
                                "destination": request.destination,
                                "intake_id": request.intake_id,
                                "classification": record["classification"],
                                "composite_score": record["composite_score"],
                                "timestamp": package.created_at.isoformat(),
                                "policy_tags": policy_tags
                            }
                            
                            encrypted_data = encrypt_data(federated_payload)
                            new_block = Block.create_new(
                                index=block_index,
                                data_encrypted=encrypted_data,
                                previous_hash=prev_hash
                            )
                            
                            # Send block only to the destination node
                            block_response = requests.post(
                                f"{destination_url}/api/v1/federated/receive_block",
                                json={
                                    "index": new_block.index,
                                    "timestamp": new_block.timestamp,
                                    "data_encrypted": new_block.data_encrypted,
                                    "previous_hash": new_block.previous_hash,
                                    "hash": new_block.hash,
                                    "signature": new_block.signature,
                                    "public_key": new_block.public_key,
                                },
                                timeout=5.0
                            )
                            
                            if block_response.status_code == 200:
                                print(f"✓ Block sent successfully to {request.destination} node")
                            else:
                                print(f"✗ Failed to send block to {request.destination}: {block_response.status_code} - {block_response.text}")
                        else:
                            print(f"✗ Failed to fetch chain from {request.destination}: {chain_response.status_code}")
                    except requests.RequestException as e:
                        print(f"✗ Network error sending block to destination node: {e}")
                    except Exception as e:
                        print(f"✗ Error sending block to destination node: {e}")
                else:
                    print(f"✗ Unknown destination: {request.destination}")
            except Exception as e:
                # Log error but don't fail the sharing request
                print(f"✗ Failed to publish to blockchain: {e}")
        
        return package

    def _generate_summary(
        self,
        intake: ContentIntake,
        classification: str,
        composite_score: float,
        breakdown,
    ) -> str:
        metadata = intake.metadata.dict() if intake.metadata else {}
        platform = metadata.get("platform") or intake.source or "an unspecified platform"
        region = metadata.get("region") or "an unspecified region"
        score_pct = f"{max(0, min(100, round(composite_score * 100)))}%"
        heuristics = (breakdown.heuristics or [])[:2]
        if heuristics:
            heuristics_text = "; ".join(heuristics)
            heuristics_sentence = f"Key signals: {heuristics_text}."
        else:
            heuristics_sentence = "No heuristics were triggered during analysis."
        ai_prob = breakdown.ai_probability
        ai_clause = ""
        if isinstance(ai_prob, (int, float)):
            ai_clause = f" AI detector confidence registered at {max(0, min(100, round(ai_prob * 100)))}%."
        return (
            f"{classification.title()} classification for a narrative originating from {region} "
            f"on {platform}. Composite risk scored {score_pct}.{ai_clause} {heuristics_sentence}"
        )

    def _build_decision_reason(
        self,
        classification: str,
        composite_score: float,
        breakdown,
    ) -> str:
        heuristics = breakdown.heuristics or []
        reason_parts: list[str] = []
        if heuristics:
            primary = "; ".join(heuristics[:3])
            reason_parts.append(f"Triggered heuristics: {primary}.")
        ai_prob = breakdown.ai_probability
        if isinstance(ai_prob, (int, float)):
            reason_parts.append(
                f"AI detector flagged a {max(0, min(100, round(ai_prob * 100)))}% likelihood."
            )
        behavior = breakdown.behavioral_score
        if isinstance(behavior, (int, float)) and behavior > 0.5:
            reason_parts.append(
                "Behavioral cues indicated urgent or coordinated language patterns."
            )
        if not reason_parts:
            reason_parts.append(
                f"Composite risk score of {max(0, min(100, round(composite_score * 100)))}% exceeded the {classification.lower()} threshold."
            )
        return " ".join(reason_parts)

    def _emit_event(self, event: Dict[str, Any]) -> None:
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest if backpressure occurs
            self._event_queue.get_nowait()
            self._event_queue.put_nowait(event)

    def _determine_policy(self, request: SharingRequest) -> list[str]:
        policy = ["classified:restricted"]
        if request.destination not in {"USA", "EU", "IN", "AUS"}:
            policy.append("export-control:review")
        if request.include_personal_data:
            policy.append("privacy:pii-included")
        else:
            policy.append("privacy:pii-redacted")
        policy.append(f"justification:{hash(request.justification) % 10000}")
        return policy
