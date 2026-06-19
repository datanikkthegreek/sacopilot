import { useEffect, useState } from "react";
import {
  AgentEvent, Health, MailItem, MeetingItem,
  getHealth, listMail, listMeetingsToday, runAgent, resolveApproval,
} from "./api";

interface Pending { id: string; tool: string; summary: string; args: Record<string, unknown>; }

// Shared agent runner: streams a task, captures log + surfaces approvals.
function useAgentRunner() {
  const [log, setLog] = useState<AgentEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);

  async function run(message: string, onDone?: () => void) {
    setBusy(true); setLog([]);
    try {
      await runAgent(message, (e) => {
        setLog((l) => [...l, e]);
        if (e.type === "approval_request") setPending(e);
      });
    } catch (e) {
      setLog((l) => [...l, { type: "error", message: String(e) }]);
    } finally {
      setBusy(false);
      onDone?.();
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!pending) return;
    await resolveApproval(pending.id, decision);
    setPending(null);
  }

  return { log, busy, pending, run, decide };
}

function ApprovalModal({ pending, decide }: { pending: Pending; decide: (d: "approve" | "reject") => void }) {
  return (
    <div className="modal-bg">
      <div className="modal">
        <h3>Approve action?</h3>
        <p>{pending.summary}</p>
        <pre>{JSON.stringify(pending.args, null, 2)}</pre>
        <div className="actions">
          <button onClick={() => decide("reject")}>Reject</button>
          <button className="primary" onClick={() => decide("approve")}>Approve</button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<"mail" | "meetings">("mail");
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth(null)); }, []);

  return (
    <div className="app">
      <header className="bar">
        <h1>SA Copilot</h1>
        <div className="tabs">
          <div className={`tab ${tab === "mail" ? "active" : ""}`} onClick={() => setTab("mail")}>Mail</div>
          <div className={`tab ${tab === "meetings" ? "active" : ""}`} onClick={() => setTab("meetings")}>Meetings</div>
        </div>
        {health && (
          <div className="health">
            <span><Dot ok={health.anthropic_key} /> model</span>
            <span><Dot ok={health.google_authed} /> google</span>
            <span><Dot ok={health.vault_found} /> vault</span>
          </div>
        )}
      </header>
      <div className="body">
        {tab === "mail"
          ? <MailView googleAuthed={health?.google_authed ?? false} />
          : <MeetingsView googleAuthed={health?.google_authed ?? false} />}
      </div>
    </div>
  );
}

function Dot({ ok }: { ok: boolean }) {
  return <span className={`dot ${ok ? "ok" : "bad"}`} />;
}

function MailView({ googleAuthed }: { googleAuthed: boolean }) {
  const [mail, setMail] = useState<MailItem[]>([]);
  const [sel, setSel] = useState<MailItem | null>(null);
  const [filters, setFilters] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const { log, busy, pending, run, decide } = useAgentRunner();

  function refresh() {
    listMail().then(setMail).catch((e) => setError(String(e)));
  }
  useEffect(() => { if (googleAuthed) refresh(); }, [googleAuthed]);

  function toggleFilter(label: string) {
    const next = new Set(filters);
    next.has(label) ? next.delete(label) : next.add(label);
    setFilters(next);
  }

  // AND across selected facets.
  const shown = mail.filter((m) => [...filters].every((f) => m.labels.includes(f)));
  const allLabels = Array.from(new Set(mail.flatMap((m) => m.labels))).sort();

  function classifyNew() {
    setError(null);
    run(
      "Classify my new inbox mail: list unclassified messages, classify each, and apply the labels.",
      refresh,
    );
  }

  if (!googleAuthed) {
    return (
      <div className="empty">
        Google not connected. Run once in the repo:<br />
        <code>uv run python -m server.google_client auth</code>
      </div>
    );
  }

  return (
    <>
      <div className="maillist">
        <div className="toolbar">
          <button className="primary" disabled={busy} onClick={classifyNew}>
            {busy ? "Classifying…" : "Classify new"}
          </button>
          <button disabled={busy} onClick={refresh}>Refresh</button>
        </div>
        {allLabels.length > 0 && (
          <div className="filters">
            <div className="chips">
              {allLabels.map((l) => (
                <span key={l} className={`chip f ${filters.has(l) ? "on" : ""}`} onClick={() => toggleFilter(l)}>{l}</span>
              ))}
            </div>
          </div>
        )}
        {error && <div className="empty">{error}</div>}
        {shown.map((m) => (
          <div key={m.id} className={`mailrow ${sel?.id === m.id ? "sel" : ""}`} onClick={() => setSel(m)}>
            <div className="from">{m.from}</div>
            <div className="subj">{m.subject}</div>
            <div className="snip">{m.snippet}</div>
            <div className="chips">
              {m.labels.map((l) => (
                <span key={l} className={`chip ${l === "Needs/Review" ? "review" : ""}`}>{l}</span>
              ))}
            </div>
          </div>
        ))}
        {shown.length === 0 && !error && <div className="empty">No messages.</div>}
      </div>

      <div className="detail">
        {sel ? (
          <>
            <h2 style={{ marginTop: 0 }}>{sel.subject}</h2>
            <div style={{ color: "var(--muted)", fontSize: 13 }}>{sel.from} · {sel.date}</div>
            <div className="chips" style={{ margin: "10px 0" }}>
              {sel.labels.map((l) => <span key={l} className="chip">{l}</span>)}
            </div>
            <p>{sel.snippet}</p>
          </>
        ) : (
          <div className="log">
            {log.length === 0 && <div className="empty">Select an email, or click "Classify new".</div>}
            {log.map((e, i) => <LogLine key={i} e={e} />)}
          </div>
        )}
      </div>

      {pending && <ApprovalModal pending={pending} decide={decide} />}
    </>
  );
}

function LogLine({ e }: { e: AgentEvent }) {
  if (e.type === "text") return <div>{e.text}</div>;
  if (e.type === "tool_use") return <div className="tool">→ {e.tool}({Object.keys(e.args).join(", ")})</div>;
  if (e.type === "tool_result")
    return <div className="tool">  {e.skipped ? "skipped" : e.error ? `error: ${e.error}` : "ok"}</div>;
  if (e.type === "error") return <div className="err">{e.message}</div>;
  return null;
}

function MeetingsView({ googleAuthed }: { googleAuthed: boolean }) {
  const [meetings, setMeetings] = useState<MeetingItem[]>([]);
  const [sel, setSel] = useState<MeetingItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { log, busy, pending, run, decide } = useAgentRunner();

  useEffect(() => {
    if (googleAuthed) listMeetingsToday().then(setMeetings).catch((e) => setError(String(e)));
  }, [googleAuthed]);

  function prep(m: MeetingItem) {
    run(`Prepare for the meeting "${m.summary}" (${m.start}). Search the vault for relevant context and recent meetings, then draft a short agenda/brief.`);
  }
  function capture(m: MeetingItem) {
    run(`Capture notes for "${m.summary}" (${m.start}): find its Gemini meeting doc in Drive, export it, and propose a filed meeting note (and any contact/project updates) as diffs for my review.`);
  }
  function followup(m: MeetingItem) {
    run(`Draft a follow-up email for "${m.summary}" in my voice, based on the meeting notes. Create it as a Gmail draft.`);
  }

  if (!googleAuthed) {
    return (
      <div className="empty">
        Google not connected. Run once: <code>uv run python -m server.google_client auth</code>
      </div>
    );
  }

  return (
    <>
      <div className="maillist">
        {error && <div className="empty">{error}</div>}
        {meetings.map((m) => (
          <div key={m.id} className={`mailrow ${sel?.id === m.id ? "sel" : ""}`} onClick={() => setSel(m)}>
            <div className="from">{m.start?.slice(11, 16) || ""} · {m.summary}</div>
            <div className="snip">{m.attendees.slice(0, 4).join(", ")}</div>
            <div className="toolbar" style={{ border: 0, padding: "6px 0 0" }}>
              <button disabled={busy} onClick={(e) => { e.stopPropagation(); prep(m); }}>Prep</button>
              <button disabled={busy} onClick={(e) => { e.stopPropagation(); capture(m); }}>Notes</button>
              <button disabled={busy} onClick={(e) => { e.stopPropagation(); followup(m); }}>Follow-up</button>
            </div>
          </div>
        ))}
        {meetings.length === 0 && !error && <div className="empty">No meetings today.</div>}
      </div>
      <div className="detail">
        <div className="log">
          {log.length === 0 && <div className="empty">Pick a meeting and run Prep / Notes / Follow-up.</div>}
          {log.map((e, i) => <LogLine key={i} e={e} />)}
        </div>
      </div>
      {pending && <ApprovalModal pending={pending} decide={decide} />}
    </>
  );
}
