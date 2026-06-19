// Backend API client. Streams agent events via SSE-over-fetch (POST + ReadableStream).

export type AgentEvent =
  | { type: "text"; text: string }
  | { type: "tool_use"; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; tool: string; result?: unknown; error?: string; skipped?: boolean }
  | { type: "approval_request"; id: string; tool: string; summary: string; args: Record<string, unknown> }
  | { type: "done"; stop_reason: string }
  | { type: "error"; message: string }
  | { type: "end" };

export interface Health {
  status: string;
  model: string;
  anthropic_key: boolean;
  google_authed: boolean;
  vault_found: boolean;
  voice_profile_found: boolean;
}

export async function getHealth(): Promise<Health> {
  const r = await fetch("/health");
  return r.json();
}

// Run the agent; invokes onEvent for each streamed event.
export async function runAgent(
  message: string,
  onEvent: (e: AgentEvent) => void,
  history?: unknown[],
): Promise<void> {
  const resp = await fetch("/api/agent/message", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!resp.body) throw new Error("no response body");
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as AgentEvent);
      } catch {
        /* ignore malformed keepalive */
      }
    }
  }
}

export async function resolveApproval(
  id: string,
  decision: "approve" | "reject",
  editedArgs?: Record<string, unknown>,
): Promise<void> {
  await fetch("/api/agent/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, decision, edited_args: editedArgs ?? null }),
  });
}

// --- Mail (Phase 5 read endpoints; backed by routes/mail.py) ---------------
export interface MailItem {
  id: string;
  thread_id: string;
  subject: string;
  from: string;
  date: string;
  snippet: string;
  labels: string[]; // taxonomy label names currently on the message
}

export async function listMail(query = "in:inbox", max = 30): Promise<MailItem[]> {
  const r = await fetch(`/api/mail/list?query=${encodeURIComponent(query)}&max_results=${max}`);
  if (!r.ok) throw new Error(`mail/list ${r.status}`);
  return r.json();
}

// --- Meetings --------------------------------------------------------------
export interface MeetingItem {
  id: string;
  summary: string;
  start: string;
  end: string;
  attendees: string[];
  hangout?: string;
}

export async function listMeetingsToday(): Promise<MeetingItem[]> {
  const r = await fetch("/api/meetings/today");
  if (!r.ok) throw new Error(`meetings/today ${r.status}`);
  return r.json();
}
