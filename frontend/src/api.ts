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

// --- Mail (backed by routes/mail.py) ---------------------------------------
export interface Facets {
  type: string;
  org: string;
  prio: string;
  dbx: string | null;
  bosch: string | null;
  bu: string[];
  labels: string[];
  confidence?: number;
  needs_review?: boolean;
  adjusted?: boolean;
}

// A conversation (thread) row in the list (served from the Lakebase cache).
export interface Thread {
  thread_id: string;
  subject: string;
  from: string;
  snippet: string;
  message_count: number;
  date: string | null;     // ISO of the latest message
  internal_date: number | null;
  unread: boolean;
  status: string;          // Open | In Progress | Completed
  labels: string[];        // effective taxonomy labels (from Lakebase)
  classified: boolean;
  adjusted: boolean;
  facets: Facets | null;   // null until classified; powers the dropdown editor
}

export interface ThreadMessage {
  message_id: string;
  ordinal: number;
  from_addr: string;
  to_addr: string;
  date_str: string;
  internal_date: number;
  subject: string;
  snippet: string;
  body_html: string | null;
  body_text: string | null;
}

export interface ThreadDetail {
  thread_id: string;
  messages: ThreadMessage[];
  facets: Facets | null;
}

export interface InboxCounts { total: number; unread: number; classified: number; }

export interface ThreadPage {
  threads: Thread[];
  counts: InboxCounts;
  has_more: boolean;
}

export interface Taxonomy {
  type: string[]; org: string[]; prio: string[];
  dbx: string[]; bosch: string[]; bu: string[];
}

export type ClassifyEvent =
  | { type: "start"; total: number }
  | { type: "progress"; done: number; total: number; thread_id: string; labels: string[]; facets: Facets; needs_review: boolean }
  | { type: "item_error"; done: number; total: number; thread_id: string; message: string }
  | { type: "done"; total: number }
  | { type: "error"; message: string };

export type SyncEvent =
  | { type: "phase"; phase: string }
  | { type: "start"; total: number; inbox: number; archived: number }
  | { type: "progress"; done: number; total: number; thread_id: string }
  | { type: "item_error"; done: number; total: number; thread_id: string; message: string }
  | { type: "done"; total: number; inbox: number; archived: number }
  | { type: "error"; message: string };

export async function listThreads(offset = 0, opts: { unread?: boolean; status?: string; label?: string; limit?: number } = {}): Promise<ThreadPage> {
  const p = new URLSearchParams({ offset: String(offset), limit: String(opts.limit ?? 100) });
  if (opts.unread) p.set("unread", "true");
  if (opts.status) p.set("status", opts.status);
  if (opts.label) p.set("label", opts.label);
  const r = await fetch(`/api/mail/threads?${p}`);
  if (!r.ok) throw new Error(`mail/threads ${r.status}`);
  return r.json();
}

export async function getThread(threadId: string): Promise<ThreadDetail> {
  const r = await fetch(`/api/mail/thread/${encodeURIComponent(threadId)}`);
  if (!r.ok) throw new Error(`mail/thread ${r.status}`);
  return r.json();
}

// Sync the inbox into Lakebase; invokes onEvent for each streamed event.
export async function syncMail(onEvent: (e: SyncEvent) => void): Promise<void> {
  await streamSse("/api/mail/sync", (o) => onEvent(o as SyncEvent));
}

export async function getTaxonomy(): Promise<Taxonomy> {
  const r = await fetch("/api/mail/taxonomy");
  if (!r.ok) throw new Error(`mail/taxonomy ${r.status}`);
  return r.json();
}

// Shared SSE-over-fetch reader (POST). Invokes onEvent per parsed data event.
async function streamSse(url: string, onEvent: (o: unknown) => void): Promise<void> {
  const resp = await fetch(url, { method: "POST" });
  if (!resp.body) throw new Error(`${url} ${resp.status}`);
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
        onEvent(JSON.parse(line.slice(5).trim()));
      } catch {
        /* ignore malformed keepalive */
      }
    }
  }
}

// Batch-classify unclassified conversations; invokes onEvent for each event.
export async function classifyMail(onEvent: (e: ClassifyEvent) => void): Promise<void> {
  await streamSse("/api/mail/classify", (o) => onEvent(o as ClassifyEvent));
}

export interface ReplyDraft {
  thread_id: string;
  to: string;
  subject: string;
  draft_text: string;
  draft_id: string | null;
  sources: { title: string; url: string; snippet: string }[];
  glean_used: boolean;
}

// Draft a reply (full thread + Glean + voice) and save it as a Gmail draft.
export async function draftReply(threadId: string): Promise<ReplyDraft> {
  const r = await fetch(`/api/mail/reply/${encodeURIComponent(threadId)}`, { method: "POST" });
  if (!r.ok) throw new Error(`mail/reply ${r.status}`);
  return r.json();
}

// Set a conversation's workflow status. Completed archives it in Gmail.
export async function setStatus(
  threadId: string, status: string,
): Promise<{ thread_id: string; status: string; archived: boolean }> {
  const r = await fetch(`/api/mail/status/${encodeURIComponent(threadId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`mail/status ${r.status}`);
  return r.json();
}

// Manually correct a conversation's classification; returns regenerated labels.
export async function updateClassification(
  threadId: string,
  facets: Pick<Facets, "type" | "org" | "prio" | "dbx" | "bosch" | "bu">,
): Promise<{ thread_id: string; labels: string[]; adjusted: boolean }> {
  const r = await fetch(`/api/mail/classify/${encodeURIComponent(threadId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(facets),
  });
  if (!r.ok) throw new Error(`mail/classify PUT ${r.status}`);
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
