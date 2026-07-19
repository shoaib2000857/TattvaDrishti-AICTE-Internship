export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// Map destinations to node base URLs; fall back to API_BASE_URL if unset
export const DESTINATION_NODE_URLS = {
  USA: process.env.NEXT_PUBLIC_NODE1_URL || "http://localhost:8001",
  EU: process.env.NEXT_PUBLIC_NODE2_URL || "http://localhost:8002",
  IN: process.env.NEXT_PUBLIC_NODE3_URL || "http://localhost:8003",
  AUS: process.env.NEXT_PUBLIC_NODE4_URL || "http://localhost:8004",
};

const headers = {
  "Content-Type": "application/json",
};

export async function submitIntake(payload) {
  const res = await fetch(`${API_BASE_URL}/api/v1/intake`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function submitBatchFile({
  file,
  sourceSystem,
  collectionId,
  classificationMarking,
}) {
  const body = new FormData();
  body.append("file", file);
  body.append("source_system", sourceSystem || "file-upload");
  if (collectionId) body.append("collection_id", collectionId);
  if (classificationMarking) body.append("classification_marking", classificationMarking);
  const res = await fetch(`${API_BASE_URL}/api/v1/intake/batch/file`, {
    method: "POST",
    body,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function ingestTelegramLink(payload) {
  const res = await fetch(`${API_BASE_URL}/api/ingest/telegram`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      message = data?.detail?.message || data?.detail || message;
    } catch (error) {
      message = await res.text();
    }
    throw new Error(message || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchCase(intakeId) {
  const res = await fetch(`${API_BASE_URL}/api/v1/cases/${encodeURIComponent(intakeId)}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function requestSharingPackage(payload) {
  // Always use main API for sharing - it has the case data
  const res = await fetch(`${API_BASE_URL}/api/v1/share`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

// Simple Server-Sent Events (SSE) stream for live updates
export function createEventStream(onEvent, onError) {
  const url = `${API_BASE_URL}/api/v1/events/stream`;
  const source = new EventSource(url);

  source.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent && onEvent(data);
    } catch (err) {
      console.error("Failed to parse event", err);
    }
  };

  source.onerror = () => {
    onError && onError();
  };

  return source;
}
