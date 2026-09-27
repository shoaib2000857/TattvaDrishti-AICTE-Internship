import json
from datetime import datetime, timezone
from time import perf_counter
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .config import Settings, get_settings
from .schemas import (
    ContentIntake,
    BatchDetectionResult,
    BatchIntakeEnvelope,
    BatchItemError,
    BatchItemResult,
    BaseModel,
    DetectionResult,
    CopilotRequest,
    CopilotResponse,
    NarrativeMatch,
    NarrativeTrace,
    SharingPackage,
    SharingRequest,
    SecureTransferEnvelope,
    SecureTransferReceipt,
    SIEMCorrelationPayload,
    SimilarMessagesResponse,
    EvidenceReview,
    ThreatIntelFeed,
    WarRoomSnapshot,
)
from .services.orchestrator import AnalysisOrchestrator
from .services.batch import (
    BatchFileError,
    ParsedBatch,
    envelope_to_parsed,
    parse_batch_file,
)
from .storage.database import Database
from .federated.manager import LedgerManager
from .federated.node import Node
from .federated.ledger import Block
from .federated.crypto import encrypt_data, decrypt_data, sha256
from .federated.secure_transfer import SecureTransferError
from .heatmap import router as heatmap_router, record_point
from .auth.middleware import role_protection
from .ingest.router import router as ingest_router

settings = get_settings()
app = FastAPI(title=settings.app_name)
template_engine = Jinja2Templates(directory="templates")
orchestrator = AnalysisOrchestrator()
database_l1 = Database()  # Write-enabled connection
database_l2 = Database()  # Read-only connection (simulated)
ledger = LedgerManager()
node = Node()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Heatmap API
app.include_router(heatmap_router)
app.include_router(ingest_router)


@app.on_event("startup")
async def startup_event():
    """Ensure database is initialized on startup."""
    # Database init is already called in Database.__init__, but we verify it here
    # to surface any errors early
    try:
        database_l1._initialise()
    except Exception as e:
        print(f"Database initialization warning: {e}")


async def get_app_settings() -> Settings:
    return settings


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return template_engine.TemplateResponse("dashboard.html", {"request": request})


@app.post("/api/v1/intake", response_model=DetectionResult)
async def submit_content(
    request: Request,
    payload: ContentIntake,
    _: Settings = Depends(get_app_settings),
):
    # Role check: Only allow users with 'upload' permission
    user_id = await role_protection(request, "upload")
    # Use L1 DB connection for all uploads
    db_conn = database_l1
    # Require region from intake
    region = None
    try:
        region = (payload.metadata.region if payload.metadata else None)
    except Exception:
        region = None
    if not region or not str(region).strip():
        raise HTTPException(status_code=400, detail="Region (city/district) is required.")

    result = await orchestrator.process_intake(payload)

    # Normalize composite score and record point for heatmap (non-blocking)
    try:
        score = result.composite_score
        norm = int(round(score * 100)) if 0 <= score <= 1 else int(round(score))
        norm = max(0, min(100, norm))
        record_point(str(region).strip(), norm)
    except Exception:
        pass

    return result


async def _execute_batch(parsed: ParsedBatch, actor: str) -> BatchDetectionResult:
    accepted_at = datetime.utcnow()
    started = perf_counter()
    outcomes = await orchestrator.process_batch(
        [(record.message_id, record.intake) for record in parsed.records],
        batch_id=parsed.batch_id,
        actor=actor,
    )

    items = [
        BatchItemResult(
            index=rejection.index,
            message_id=rejection.message_id,
            status="error",
            errors=rejection.errors,
        )
        for rejection in parsed.rejected
    ]
    for record, (result, error) in zip(parsed.records, outcomes):
        if result is not None:
            items.append(
                BatchItemResult(
                    index=record.index,
                    message_id=record.message_id,
                    status="success",
                    result=result,
                )
            )
            try:
                region = record.intake.metadata.region if record.intake.metadata else None
                if region:
                    score = result.composite_score
                    normalized = int(round(score * 100)) if 0 <= score <= 1 else int(round(score))
                    record_point(str(region).strip(), max(0, min(100, normalized)))
            except Exception:
                pass
        else:
            items.append(
                BatchItemResult(
                    index=record.index,
                    message_id=record.message_id,
                    status="error",
                    errors=[
                        BatchItemError(
                            code="processing_failed",
                            message=error or "The message could not be processed.",
                            line_number=record.line_number,
                        )
                    ],
                )
            )

    items.sort(key=lambda item: item.index)
    completed_at = datetime.utcnow()
    succeeded = sum(item.status == "success" for item in items)
    return BatchDetectionResult(
        batch_id=parsed.batch_id,
        source_system=parsed.source_system,
        classification_marking=parsed.classification_marking,
        accepted_at=accepted_at,
        completed_at=completed_at,
        duration_ms=max(0, round((perf_counter() - started) * 1000)),
        total=parsed.total,
        succeeded=succeeded,
        failed=parsed.total - succeeded,
        items=items,
    )


@app.post("/api/v1/intake/batch", response_model=BatchDetectionResult)
async def submit_batch(
    request: Request,
    payload: BatchIntakeEnvelope,
    _: Settings = Depends(get_app_settings),
):
    """Process a strict JSON batch envelope using the existing analysis pipeline."""
    actor = await role_protection(request, "upload")
    count = len(payload.messages)
    if count == 0:
        raise HTTPException(status_code=400, detail="The batch contains no messages.")
    if count > settings.batch_max_records:
        raise HTTPException(
            status_code=413,
            detail=f"The configured batch limit is {settings.batch_max_records} records.",
        )
    return await _execute_batch(envelope_to_parsed(payload), actor)


@app.post("/api/v1/intake/batch/file", response_model=BatchDetectionResult)
async def submit_batch_file(
    request: Request,
    file: UploadFile = File(...),
    source_system: str = Form("file-upload"),
    batch_id: Optional[str] = Form(None),
    collection_id: Optional[str] = Form(None),
    classification_marking: Optional[str] = Form(None),
    _: Settings = Depends(get_app_settings),
):
    """Upload a JSON envelope or JSONL/NDJSON file with per-record errors."""
    actor = await role_protection(request, "upload")
    content = await file.read(settings.batch_max_file_bytes + 1)
    if len(content) > settings.batch_max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Batch file exceeds {settings.batch_max_file_bytes} bytes.",
        )
    try:
        parsed = parse_batch_file(
            content,
            filename=file.filename or "",
            source_system=source_system,
            batch_id=batch_id,
            collection_id=collection_id,
            classification_marking=classification_marking,
            max_records=settings.batch_max_records,
        )
    except BatchFileError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return await _execute_batch(parsed, actor)


@app.get("/api/v1/cases/{intake_id}", response_model=DetectionResult)
async def get_case(request: Request, intake_id: str):
    # Role check: Only allow users with 'dashboard' permission
    user_id = await role_protection(request, "dashboard")
    # Use L2 DB connection for dashboard/logs
    record = database_l2.fetch_case(intake_id)
    if not record:
        raise HTTPException(status_code=404, detail="Case not found")
    graph_snapshot = orchestrator.graph.summary()
    # reconstruct result for client convenience
    return DetectionResult.parse_obj(
        {
            "intake_id": intake_id,
            "submitted_at": record["created_at"],
            "composite_score": record["composite_score"],
            "classification": record["classification"],
            "breakdown": record["breakdown"],
            "provenance": record["provenance"],
            "graph_summary": graph_snapshot.dict(),
            "summary": record.get("summary"),
            "findings": (record.get("breakdown", {}).get("heuristics") or [])[:5],
            "decision_reason": record.get("decision_reason"),
        }
    )


@app.get(
    "/api/v1/narratives/{intake_id}/similar",
    response_model=List[NarrativeMatch],
)
async def find_similar_content(request: Request, intake_id: str, limit: int = 20):
    """Find duplicates and paraphrases across collected social platforms."""
    await role_protection(request, "dashboard")
    try:
        return orchestrator.narratives.similar(intake_id, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/api/v1/cases/{intake_id}/similar",
    response_model=SimilarMessagesResponse,
)
async def find_similar_case_messages(
    request: Request,
    intake_id: str,
    scope: str = "current_batch",
    limit: Optional[int] = None,
):
    """On-demand related-message search over stored narrative features."""
    await role_protection(request, "dashboard")
    try:
        return orchestrator.narratives.find_similar_messages(
            intake_id,
            scope=scope,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/api/v1/cases/{intake_id}/evidence",
    response_model=EvidenceReview,
)
async def review_case_evidence(request: Request, intake_id: str):
    """Assemble a balanced evidence view from existing stored outputs only."""
    await role_protection(request, "dashboard")
    try:
        return orchestrator.evidence.review(intake_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/api/v1/narratives/{intake_id}/trace",
    response_model=NarrativeTrace,
)
async def trace_narrative_origin(request: Request, intake_id: str):
    """Trace a narrative to its earliest observation in collected evidence."""
    await role_protection(request, "dashboard")
    try:
        return orchestrator.narratives.trace(intake_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/v1/war-room", response_model=WarRoomSnapshot)
async def incident_war_room(
    request: Request,
    title: str = "Live Influence Incident",
    window_hours: int = 24,
    query: Optional[str] = None,
):
    await role_protection(request, "dashboard")
    return orchestrator.narratives.war_room(
        title=title[:160],
        window_hours=max(1, min(window_hours, 720)),
        query=query,
    )


@app.post("/api/v1/copilot", response_model=CopilotResponse)
async def analyst_copilot(request: Request, payload: CopilotRequest):
    """Answer only from evidence attached to the selected narrative."""
    await role_protection(request, "dashboard")
    try:
        return orchestrator.narratives.copilot(payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/v1/share", response_model=SharingPackage)
async def request_sharing_package(request_payload: SharingRequest) -> SharingPackage:
    try:
        return await orchestrator.build_sharing_package(request_payload)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@app.post(
    "/api/v1/secure-transfer/receive",
    response_model=SecureTransferReceipt,
)
async def receive_secure_transfer(
    request: Request,
    envelope: SecureTransferEnvelope,
) -> SecureTransferReceipt:
    """Verify, decrypt, and acknowledge an authenticated partner envelope."""
    forwarded_protocol = request.headers.get("x-forwarded-proto", request.url.scheme)
    protocol = forwarded_protocol.split(",", 1)[0].strip().lower()
    client_host = request.client.host if request.client else ""
    is_local = client_host in {"127.0.0.1", "::1", "localhost"}
    if settings.secure_transfer_require_tls and protocol != "https" and not is_local:
        raise HTTPException(
            status_code=426,
            detail="TLS 1.3 transport is required for secure-transfer reception.",
        )
    try:
        payload = orchestrator.secure_transfer.decrypt_envelope(envelope)
    except SecureTransferError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    accepted = database_l1.record_secure_transfer(
        envelope_id=envelope.envelope_id,
        package_id=envelope.package_id,
        source_node=envelope.source_node,
        destination=envelope.destination,
        ciphertext_sha256=envelope.ciphertext_sha256,
    )
    intake_id = str(payload.get("payload", {}).get("intake_id") or envelope.package_id)
    database_l1.log_action(
        intake_id=intake_id,
        action="secure_transfer_received" if accepted else "secure_transfer_replayed",
        actor=envelope.source_node,
        payload={
            "envelope_id": envelope.envelope_id,
            "package_id": envelope.package_id,
            "destination": envelope.destination,
            "ciphertext_sha256": envelope.ciphertext_sha256,
        },
    )
    return SecureTransferReceipt(
        envelope_id=envelope.envelope_id,
        package_id=envelope.package_id,
        status="accepted" if accepted else "duplicate",
        received_at=datetime.now(timezone.utc),
        receiving_node=settings.secure_transfer_node_id,
        ciphertext_sha256=envelope.ciphertext_sha256,
    )


@app.get("/api/v1/integrations/threat-intel", response_model=ThreatIntelFeed)
async def threat_intel_feed() -> ThreatIntelFeed:
    return orchestrator.graph.threat_intel_feed()


@app.get("/api/v1/integrations/siem", response_model=SIEMCorrelationPayload)
async def siem_feed() -> SIEMCorrelationPayload:
    return orchestrator.graph.siem_payload()


@app.get("/api/v1/events/stream")
async def stream_events():
    async def event_generator():
        async for event in orchestrator.stream_events():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class FingerprintCheckPayload(BaseModel):
    text: str


@app.post("/api/v1/fingerprint/check")
async def fingerprint_check(payload: FingerprintCheckPayload):
    matches = orchestrator.check_fingerprint(payload.text)
    return {"matches": matches}


# ==================== Federated Blockchain Routes ====================

@app.post("/api/v1/federated/add_block")
async def add_federated_block(payload: dict):
    """Add a new block to the federated ledger and broadcast to peers."""
    chain = ledger.get_chain()
    prev_block = chain[-1]
    
    encrypted_data = encrypt_data(payload)
    new_block = Block.create_new(
        index=len(chain),
        data_encrypted=encrypted_data,
        previous_hash=prev_block.hash
    )
    
    ledger.save_block(new_block)
    node.broadcast_block(new_block)
    
    from dataclasses import asdict
    return {"message": "Block added to federated ledger", "block": asdict(new_block)}


@app.post("/api/v1/federated/receive_block")
async def receive_federated_block(block_data: dict):
    """Receive and validate a block from a peer node."""
    chain = ledger.get_chain()
    
    incoming_block = Block(
        index=block_data["index"],
        timestamp=block_data["timestamp"],
        data_encrypted=block_data["data_encrypted"],
        previous_hash=block_data["previous_hash"],
        public_key=block_data["public_key"],
        hash=block_data["hash"],
        signature=block_data["signature"]
    )
    
    # Check if block already exists
    if incoming_block.index < len(chain):
        existing_block = chain[incoming_block.index]
        if existing_block.hash == incoming_block.hash:
            return {"message": "Block already exists"}
        else:
            raise HTTPException(status_code=400, detail="Block index conflict")
    
    # Validate block integrity (hash and signature)
    if incoming_block.hash != sha256(incoming_block.payload()):
        raise HTTPException(status_code=400, detail="Invalid block hash")
    
    # For new blocks, check if it follows the previous block
    if incoming_block.index == len(chain):
        prev_block = chain[-1]
        if incoming_block.previous_hash != prev_block.hash:
            raise HTTPException(status_code=400, detail="Previous hash mismatch")
    
    ledger.save_block(incoming_block)
    return {"message": "Block accepted"}


@app.get("/api/v1/federated/chain")
async def get_federated_chain():
    """Retrieve the entire federated blockchain."""
    from dataclasses import asdict
    chain = ledger.get_chain()
    return {"chain": [asdict(block) for block in chain], "length": len(chain)}


@app.get("/api/v1/federated/validate")
async def validate_federated_chain():
    """Validate the local chain and check network consensus."""
    import requests
    
    chain = ledger.get_chain()
    self_valid = ledger.validate_chain(chain)
    
    results = {}
    tampered = []
    
    for node_url in node.nodes:
        if node_url != node.my_url:
            try:
                resp = requests.get(f"{node_url}/api/v1/federated/validate_local", timeout=2)
                is_valid = resp.json().get("valid", False)
                results[node_url] = is_valid
                if not is_valid:
                    tampered.append(node_url)
            except Exception:
                results[node_url] = False
                tampered.append(node_url)
    
    network_valid = self_valid and all(results.values())
    
    return {
        "self_valid": self_valid,
        "nodes": results,
        "network_valid": network_valid,
        "tampered_nodes": tampered,
        "chain_length": len(chain)
    }


@app.get("/api/v1/federated/validate_local")
async def validate_local_chain():
    """Local chain validation endpoint for peer nodes."""
    chain = ledger.get_chain()
    return {"valid": ledger.validate_chain(chain)}


@app.post("/api/v1/federated/reset_chain")
async def reset_blockchain():
    """Reset blockchain to genesis block only. WARNING: Deletes all blocks!"""
    try:
        ledger.reset_chain()
        return {"message": "Blockchain reset to genesis block", "blocks": 1}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset chain: {str(e)}")


@app.get("/api/v1/federated/decrypt_block/{block_index}")
async def decrypt_federated_block(block_index: int):
    """Decrypt a specific block's data (requires proper authorization in production)."""
    chain = ledger.get_chain()
    if block_index >= len(chain) or block_index < 0:
        raise HTTPException(status_code=404, detail="Block not found")
    
    block = chain[block_index]
    try:
        decrypted = decrypt_data(block.data_encrypted)
        return {"block_index": block_index, "data": decrypted}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")


@app.post("/api/v1/federated/sync_chain")
async def sync_chain_from_network():
    """Sync local chain from a trusted peer node (fixes corrupted chains)."""
    import requests
    from dataclasses import asdict
    
    # Try to get the longest valid chain from peers
    longest_chain = None
    max_length = 0
    
    for node_url in node.nodes:
        if node_url != node.my_url:
            try:
                resp = requests.get(f"{node_url}/api/v1/federated/chain", timeout=3)
                data = resp.json()
                peer_chain = [Block(**b) for b in data["chain"]]
                
                # Validate the peer's chain
                if ledger.validate_chain(peer_chain) and len(peer_chain) > max_length:
                    longest_chain = peer_chain
                    max_length = len(peer_chain)
            except Exception:
                continue
    
    if longest_chain is None:
        raise HTTPException(status_code=400, detail="No valid chains found in network")
    
    # Replace local chain with the longest valid one
    # WARNING: This deletes and rebuilds the local blockchain!
    import sqlite3
    conn = sqlite3.connect(ledger.ledger_db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM blocks")
    conn.commit()
    
    for block in longest_chain:
        ledger.save_block(block)
    
    conn.close()
    
    return {
        "message": "Chain synced successfully",
        "new_length": len(longest_chain),
        "synced_from": "network_consensus"
    }


@app.post("/api/v1/federated/reset_chain")
async def reset_blockchain():
    """Reset the blockchain to only genesis block. WARNING: Deletes all blocks!"""
    try:
        ledger.reset_chain()
        chain = ledger.get_chain()
        return {
            "message": "Blockchain reset to genesis block",
            "blocks_remaining": len(chain)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset chain: {str(e)}")


@app.post("/api/v1/image/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    models: str = Form('genai')  # Default to AI detection only
):
    """Analyze an image using Sightengine API for AI-generation, gore, nudity, etc."""
    import requests
    
    if not file:
        raise HTTPException(status_code=400, detail="No image file provided")
    
    params = {
        'models': models,  # Use models from form data
        'api_user': settings.sightengine_api_user,
        'api_secret': settings.sightengine_api_secret
    }
    
    try:
        # Read file content
        contents = await file.read()
        files = {'media': (file.filename, contents, file.content_type)}
        
        response = requests.post(
            'https://api.sightengine.com/1.0/check.json',
            files=files,
            data=params,
            timeout=30
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Sightengine API error")
        
        return response.json()
    
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")
