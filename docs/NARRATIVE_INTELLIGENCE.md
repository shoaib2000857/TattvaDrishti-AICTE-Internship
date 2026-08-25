# Cross-platform narrative intelligence

TattvaDrishti now builds a persistent semantic evidence graph while the normal
single-message or batch detection pipeline runs. No extra model call is made per
message: matching uses bounded, concept-normalised lexical, entity, character,
and analyst-tag signals after the detection result is available.

## Demo

Start the API and frontend normally, then upload
`samples/cross_platform_incident_batch.json` from the batch intake panel. The
file contains two separate narratives moving through Telegram, WhatsApp,
Reddit, and X. Select any resulting case to open its narrative trace and the
evidence-bounded analyst copilot.

## API

- `GET /api/v1/narratives/{intake_id}/similar` returns the closest duplicates
  and paraphrases.
- `GET /api/v1/narratives/{intake_id}/trace` returns ordered observations,
  cross-platform movement, actors, regions, velocity, and the earliest collected
  observation.
- `GET /api/v1/war-room?title=...&window_hours=168&query=...` returns incident
  totals, clusters, priority actors, hotspots, platform counts, and timeline.
- `POST /api/v1/copilot` accepts `{"intake_id":"...","question":"..."}` and
  answers only from the selected evidence cluster.

“Origin” deliberately means the earliest observation in the evidence collected
by this system. It is not presented as proof of authorship. The response includes
this caveat and a confidence score derived from available source metadata and
cluster coverage.

## Scale controls

- Candidate selection uses an in-memory inverted index and compares at most
  `NARRATIVE_CANDIDATES_PER_ITEM` records per message.
- Only `NARRATIVE_NEIGHBORS_PER_ITEM` strongest edges are persisted.
- Graph aggregation is sparse (`O(nodes + edges)` memory) and does not import
  PyTorch or allocate a dense adjacency matrix.
- Batch inference behavior is unchanged: Ollama micro-batches remain shared by
  multiple messages, and narrative matching does not create Ollama calls.

Tune thresholds in `.env`; the committed defaults are intended as conservative
demo defaults and should be calibrated on each agency's labelled corpus.
