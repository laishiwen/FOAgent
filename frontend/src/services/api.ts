import type { ClassifyResult, ProgressEvent } from "../types";

const BASE = "/api";

export interface SSEClassifyResult {
  result: ClassifyResult | null;
  error: string | null;
}

export async function* classifyStream(
  rootPath: string
): AsyncGenerator<ProgressEvent | SSEClassifyResult> {
  const res = await fetch(`${BASE}/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root_path: rootPath }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { error?: string }).error || `HTTP ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let eventType = "";
      let data = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          data = line.slice(6);
        } else if (line === "" && data) {
          try {
            const parsed = JSON.parse(data);
            if (eventType === "progress") {
              yield parsed as ProgressEvent;
            } else if (eventType === "result") {
              yield { result: parsed as ClassifyResult, error: null };
              return;
            } else if (eventType === "error") {
              yield { result: null, error: parsed.error || "error" };
              return;
            }
          } catch { /* skip */ }
          eventType = "";
          data = "";
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export const api = {
  classifyStream,
};
