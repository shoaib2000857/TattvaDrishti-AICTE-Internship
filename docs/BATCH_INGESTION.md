# Batch Message Ingestion

TattvaDrishti accepts large text collections through a versioned JSON contract. This is a project interchange format, not a claim of conformance with a government or defence standard. It is designed to preserve the identifiers and handling context commonly needed when connecting evidence exports, case-management systems, and intelligence workflows.

## Endpoints

- `POST /api/v1/intake/batch` accepts a strict JSON envelope (`application/json`). Any schema error rejects the request before analysis.
- `POST /api/v1/intake/batch/file` accepts a multipart `.json`, `.jsonl`, or `.ndjson` file. Record errors are isolated: valid records are processed and invalid records are returned with their input index and, for JSON Lines, line number.

Both endpoints require the existing `upload` permission. The single-message `/api/v1/intake` endpoint is unchanged.

## JSON envelope, schema version 1.0

See `samples/batch_intake_example.json` for a complete example.

| Field | Required | Purpose |
| --- | --- | --- |
| `schema_version` | yes | Must be `"1.0"`; enables future compatible evolution. |
| `batch_id` | no | Caller-supplied collection/run identifier; a UUID is generated when omitted. |
| `source_system` | yes | Exporting system or connector name. |
| `collection_id` | no | Upstream evidence/collection identifier. |
| `classification_marking` | no | Handling label preserved as metadata; this does not itself enforce access control. |
| `defaults` | no | Default language, source, metadata, and tags inherited by messages. |
| `messages` | yes | Ordered array of message records. |

Each message requires an upstream `message_id` and `text` between 20 and 20,000 characters. Message IDs should be stable and unique within the upstream collection. Optional fields are `conversation_id`, `observed_at` (ISO 8601), `language`, `source`, `metadata`, and `tags`. Metadata supports `platform`, `region`, `actor_id`, `related_urls`, and an `attributes` object for source-specific fields.

Defaults are filled first, then record-level metadata overrides them. Lineage fields (`message_id`, `conversation_id`, `observed_at`, `source_system`, `collection_id`, and `classification_marking`) are persisted with the case. `batch_id` and external `message_id` are also stored in indexed case columns and included in the audit event.

## JSON Lines

JSON Lines is recommended for generated exports because each line is independently recoverable and can be validated without rejecting the full file. Each non-blank line contains one message object matching the message schema. See `samples/batch_intake_example.jsonl`.

Envelope-level values are multipart fields for JSON Lines:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/intake/batch/file \
  -F 'file=@samples/batch_intake_example.jsonl;type=application/x-ndjson' \
  -F 'source_system=agency-chat-export' \
  -F 'collection_id=collection-8842' \
  -F 'classification_marking=OFFICIAL:SENSITIVE'
```

Upload a JSON envelope with:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/intake/batch \
  -H 'Content-Type: application/json' \
  --data-binary @samples/batch_intake_example.json
```

## Processing and backpressure

The pipeline uses three bounded stages:

1. Stylometric and behavioral feature preparation uses a bounded thread pool.
2. Hugging Face inference tokenizes multiple messages together and runs tensor batches. Model forward passes are locked so batch and single-message requests cannot race on a shared GPU.
3. Ollama semantic calls use bounded parallel requests. Graph mutation and SQLite persistence remain ordered to keep their shared state consistent. The graph/GNN summary is computed once after all valid records, rather than recomputed after every inserted message; every successful item receives that consistent post-batch snapshot.

Configuration:

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `BATCH_MAX_RECORDS` | 5000 | Maximum non-blank records in one request. |
| `BATCH_MAX_FILE_BYTES` | 26214400 | Maximum uploaded file size (25 MiB). |
| `BATCH_PARALLELISM` | 4 | Feature-preparation worker count. |
| `BATCH_AI_MODEL_SIZE` | 16 | Transformer tensor batch size; tune to GPU memory. |
| `BATCH_OLLAMA_PARALLELISM` | 2 | Maximum simultaneous semantic-model calls. |

The response is synchronous for this increment and contains one item per input record. For substantially larger or long-running operational workloads, the next scalability boundary is an asynchronous job API backed by a durable queue/object store and PostgreSQL rather than increasing these limits indefinitely.

## Response behavior

HTTP 200 means the batch ran; inspect `succeeded`, `failed`, and each item `status`. File uploads can return mixed results. Malformed envelopes, unsupported encodings/types, oversized files, and empty batches return request-level 4xx errors. A result item includes the ordinary `DetectionResult`, so downstream consumers do not need a separate analysis schema.

Security notes:

- `classification_marking` is preserved for integration and audit purposes; enforcement must be connected to the deployment's authorization policy.
- Upstream IDs are treated as identifiers, not trusted authorization claims.
- File bytes and record counts are bounded before model execution.
- Raw messages continue to be stored in SQLite by the existing pipeline; deployments handling sensitive data should use encrypted storage, retention controls, strong identity, and a production database.
