const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Request failed");
  }
  return response.json();
}

export async function ingestDataset(limit, offset = 0, skipExisting = true, includeOriginal = true, includeSynthetic = true) {
  const params = new URLSearchParams();
  if (typeof limit === "number") params.append("limit", limit);
  params.append("offset", offset);
  params.append("skip_existing", skipExisting);
  params.append("include_original", includeOriginal);
  params.append("include_synthetic", includeSynthetic);
  
  return apiFetch(`/ingest/dataset?${params.toString()}`, { method: "POST" });
}

export async function uploadResumes(files) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return apiFetch("/ingest/upload", { method: "POST", body: form });
}

export async function runQuery(payload, onToken) {
  const response = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Query failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let metadataParsed = false;
  let candidates = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    if (!metadataParsed && buffer.includes("END_METADATA\n")) {
      const parts = buffer.split("END_METADATA\n");
      const metaBlock = parts.shift();
      if (metaBlock.startsWith("METADATA:")) {
        try {
          const metaStr = metaBlock.replace("METADATA:", "");
          const meta = JSON.parse(metaStr);
          candidates = meta.candidates || [];
          metadataParsed = true;
          buffer = parts.join("END_METADATA\n");
          onToken({ candidates });
        } catch (e) {
          console.error("Failed to parse metadata", e);
        }
      }
    } else if (metadataParsed) {
      // Send text tokens to UI
      onToken({ token: buffer });
      buffer = "";
    }
  }
  return { candidates };
}

export async function getEvaluationMetrics() {
  return apiFetch(`/evaluation`, { method: "GET" });
}

export async function getCandidate(resumeId) {
  return apiFetch(`/candidates/${resumeId}`, { method: "GET" });
}
