import { useEffect, useMemo, useRef, useState } from "react";
import DOMPurify from "dompurify";
import {
  AgentEvent, Health, MeetingItem, Facets, Taxonomy, Thread, ThreadDetail, InboxCounts,
  getHealth, listMeetingsToday, runAgent, resolveApproval,
  listThreads, getThread, classifyMail, syncMail, getTaxonomy, updateClassification, setStatus,
  draftReply, ReplyDraft,
} from "./api";

// Facet category of a label ("Type/Action" -> "Type"; "Needs/Review" -> "Needs").
const categoryOf = (label: string) => label.split("/")[0];
const CATEGORY_ORDER = ["Type", "Org", "Prio", "DBX", "Bosch", "BU", "Needs"];
const STATUSES = ["Open", "In Progress", "Completed"] as const;
const statusClass = (s: string) => "st-" + s.toLowerCase().replace(/\s+/g, "-");

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

function Chips({ labels }: { labels: string[] }) {
  return (
    <div className="chips">
      {labels.map((l) => (
        <span key={l} className={`chip cat-${categoryOf(l).toLowerCase()}`}>{l}</span>
      ))}
    </div>
  );
}

// Show a friendly display name from a raw "Name <addr>" From header.
const displayName = (from: string) => from.replace(/<[^>]*>/, "").replace(/"/g, "").trim() || from;

// Compact date: time if today, else "Jun 21", else "21.06.26".
function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (d.getFullYear() === now.getFullYear()) return d.toLocaleDateString([], { month: "short", day: "numeric" });
  return d.toLocaleDateString([], { year: "2-digit", month: "2-digit", day: "2-digit" });
}

function MailView({ googleAuthed }: { googleAuthed: boolean }) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [counts, setCounts] = useState<InboxCounts>({ total: 0, unread: 0, classified: 0 });
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [selId, setSelId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [filters, setFilters] = useState<Set<string>>(new Set());
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [reply, setReply] = useState<ReplyDraft | null>(null);
  const [replyBusy, setReplyBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tax, setTax] = useState<Taxonomy | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number; verb: string } | null>(null);
  const [showHelp, setShowHelp] = useState(false);
  const busy = progress !== null;

  // Group selected filters by category: OR within a category, AND across.
  const byCat = new Map<string, string[]>();
  filters.forEach((f) => byCat.set(categoryOf(f), [...(byCat.get(categoryOf(f)) ?? []), f]));
  const shown = threads.filter((t) =>
    [...byCat.values()].every((sel) => sel.some((f) => t.labels.includes(f))));

  const present = Array.from(new Set(threads.flatMap((t) => t.labels)));
  const groups = CATEGORY_ORDER
    .map((c) => [c, present.filter((l) => categoryOf(l) === c).sort()] as const)
    .filter(([, ls]) => ls.length > 0);

  const sel = threads.find((t) => t.thread_id === selId) ?? null;

  async function refresh(unread = unreadOnly) {
    setError(null);
    try {
      const page = await listThreads(0, { unread });
      setThreads(page.threads);
      setCounts(page.counts);
      setOffset(page.threads.length);
      setHasMore(page.has_more);
    } catch (e) { setError(String(e)); }
  }

  async function loadOlder() {
    try {
      const page = await listThreads(offset, { unread: unreadOnly });
      setThreads((prev) => {
        const seen = new Set(prev.map((t) => t.thread_id));
        return [...prev, ...page.threads.filter((t) => !seen.has(t.thread_id))];
      });
      setOffset((o) => o + page.threads.length);
      setHasMore(page.has_more);
    } catch (e) { setError(String(e)); }
  }

  function toggleUnread() {
    const next = !unreadOnly;
    setUnreadOnly(next);
    refresh(next);
  }

  async function syncNow() {
    setError(null);
    setProgress({ done: 0, total: 0, verb: "synced" });
    try {
      await syncMail((e) => {
        if (e.type === "start") setProgress({ done: 0, total: e.total, verb: "synced" });
        else if (e.type === "progress") setProgress({ done: e.done, total: e.total, verb: "synced" });
        else if (e.type === "item_error") setProgress((p) => p && { ...p, done: e.done, total: e.total });
        else if (e.type === "error") setError(e.message);
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setProgress(null);
      refresh();
    }
  }

  useEffect(() => {
    if (googleAuthed) { refresh(); getTaxonomy().then(setTax).catch(() => {}); }
  }, [googleAuthed]);

  async function onDraftReply(threadId: string) {
    setReplyBusy(true); setError(null);
    try {
      setReply(await draftReply(threadId));
    } catch (e) { setError(String(e)); }
    finally { setReplyBusy(false); }
  }

  // Load the conversation into the reading pane when the selection changes.
  useEffect(() => {
    setReply(null);
    if (!selId) { setDetail(null); return; }
    setDetailLoading(true);
    getThread(selId)
      .then((d) => setDetail(d))
      .catch((e) => setError(String(e)))
      .finally(() => setDetailLoading(false));
  }, [selId]);

  function move(delta: number) {
    if (shown.length === 0) return;
    const i = shown.findIndex((t) => t.thread_id === selId);
    const next = i < 0 ? 0 : Math.min(shown.length - 1, Math.max(0, i + delta));
    setSelId(shown[next].thread_id);
  }

  // Keyboard triage. Ignore when typing in a field.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (el && ["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName)) return;
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "c" && !busy) { classifyNew(); }
      else if (e.key === "s" && !busy) { syncNow(); }
      else if (e.key === "r") { refresh(); }
      else if (selId && e.key === "1") { onStatus(selId, "Open"); }
      else if (selId && e.key === "2") { onStatus(selId, "In Progress"); }
      else if (selId && e.key === "3") { onStatus(selId, "Completed"); }
      else if (selId && e.key === "d" && !replyBusy) { onDraftReply(selId); }
      else if (e.key === "?") { setShowHelp((s) => !s); }
      else if (e.key === "Escape") { setShowHelp(false); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function toggleFilter(label: string) {
    const next = new Set(filters);
    next.has(label) ? next.delete(label) : next.add(label);
    setFilters(next);
  }

  async function classifyNew() {
    setError(null);
    setProgress({ done: 0, total: 0, verb: "classified" });
    try {
      await classifyMail((e) => {
        if (e.type === "start") setProgress({ done: 0, total: e.total, verb: "classified" });
        else if (e.type === "progress") {
          setProgress({ done: e.done, total: e.total, verb: "classified" });
          setThreads((ts) => ts.map((t) =>
            t.thread_id === e.thread_id
              ? { ...t, classified: true, adjusted: false, labels: e.labels, facets: e.facets }
              : t));
        } else if (e.type === "item_error") setProgress((p) => p && { ...p, done: e.done, total: e.total });
        else if (e.type === "error") setError(e.message);
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setProgress(null);
      setCounts((c) => ({ ...c, classified: threads.filter((t) => t.classified).length }));
    }
  }

  async function onEdit(threadId: string, facets: Facets) {
    const { labels } = await updateClassification(threadId, facets);
    const merged = { ...facets, labels };
    setThreads((ts) => ts.map((t) =>
      t.thread_id === threadId ? { ...t, labels, adjusted: true, facets: merged } : t));
    setDetail((d) => (d && d.thread_id === threadId ? { ...d, facets: merged } : d));
  }

  async function onStatus(threadId: string, status: string) {
    try {
      const res = await setStatus(threadId, status);
      if (res.archived) {
        // Completed → leaves the inbox: drop it and advance selection.
        const idx = shown.findIndex((t) => t.thread_id === threadId);
        const nextSel = shown[idx + 1]?.thread_id ?? shown[idx - 1]?.thread_id ?? null;
        setThreads((ts) => ts.filter((t) => t.thread_id !== threadId));
        setCounts((c) => ({ ...c, total: Math.max(0, c.total - 1) }));
        if (selId === threadId) setSelId(nextSel);
      } else {
        setThreads((ts) => ts.map((t) => t.thread_id === threadId ? { ...t, status } : t));
      }
    } catch (e) { setError(String(e)); }
  }

  if (!googleAuthed) {
    return (
      <div className="empty">
        Google not connected. The dbexec MCP session is unavailable — check your Databricks CLI login.
      </div>
    );
  }

  return (
    <>
      <div className="maillist">
        <div className="toolbar">
          <button className="primary" disabled={busy} onClick={syncNow}>
            {busy && progress?.verb === "synced" ? "Syncing…" : "Sync"}
          </button>
          <button disabled={busy} onClick={classifyNew}>
            {busy && progress?.verb === "classified" ? "Classifying…" : "Classify new"}
          </button>
          <button className={unreadOnly ? "toggle on" : "toggle"} onClick={toggleUnread}>
            {unreadOnly ? "Unread ✓" : "Unread"}
          </button>
          <span className="count">
            {counts.total} mails · {counts.unread} unread · {counts.classified} classified
          </span>
          <span className="kbd-hint" onClick={() => setShowHelp(true)}>? shortcuts</span>
        </div>
        {progress && (
          <div className="progress">
            <div className="progress-bar">
              <div className="progress-fill"
                   style={{ width: progress.total ? `${(progress.done / progress.total) * 100}%` : "0%" }} />
            </div>
            <div className="progress-label">
              {progress.total === 0
                ? (progress.verb === "synced" ? "Scanning inbox…" : "Finding unclassified conversations…")
                : `${progress.done} / ${progress.total} ${progress.verb}`}
            </div>
          </div>
        )}
        {groups.length > 0 && (
          <div className="filters">
            {groups.map(([cat, labels]) => (
              <div key={cat} className="filtergroup">
                <span className="filtergroup-label">{cat}</span>
                {labels.map((l) => (
                  <span key={l}
                        className={`chip cat-${cat.toLowerCase()} f ${filters.has(l) ? "on" : ""}`}
                        onClick={() => toggleFilter(l)}>
                    {l.includes("/") ? l.split("/")[1] : l}
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
        {error && <div className="empty">{error}</div>}
        {shown.map((t) => (
          <div key={t.thread_id} className={`mailrow ${selId === t.thread_id ? "sel" : ""} ${t.unread ? "unread" : ""}`}
               onClick={() => setSelId(t.thread_id)}>
            <div className="from">
              {t.unread && <span className="unread-dot" />}
              {displayName(t.from)}
              {t.message_count > 1 && <span className="count-badge">{t.message_count}</span>}
              {t.adjusted && <span className="badge">edited</span>}
              <span className="row-date">{fmtDate(t.date)}</span>
            </div>
            <div className="subj">{t.subject}</div>
            <div className="snip">{t.snippet}</div>
            <div className="row-tags">
              {t.status !== "Open" && <span className={`chip ${statusClass(t.status)}`}>{t.status}</span>}
              {t.labels.length > 0 && <Chips labels={t.labels} />}
            </div>
          </div>
        ))}
        {threads.length === 0 && !error && (
          <div className="empty">Inbox not synced yet — click <b>Sync</b> (or press <b>s</b>).</div>
        )}
        {shown.length === 0 && threads.length > 0 && !error && <div className="empty">No matches.</div>}
        {hasMore && shown.length > 0 && (
          <div className="loadmore"><button onClick={loadOlder}>Load older</button></div>
        )}
      </div>

      <div className="detail">
        {sel ? (
          <>
            <h2 style={{ marginTop: 0 }}>{sel.subject}</h2>
            <div className="statusbar">
              {STATUSES.map((s) => (
                <button key={s}
                        className={`status-btn ${statusClass(s)} ${sel.status === s ? "on" : ""}`}
                        onClick={() => onStatus(sel.thread_id, s)}>
                  {s}
                </button>
              ))}
              <span className="hint">keys 1 / 2 / 3</span>
            </div>
            {sel.facets && tax
              ? <FacetEditor key={sel.thread_id} facets={sel.facets} tax={tax}
                             onSave={(f) => onEdit(sel.thread_id, f)} />
              : <div className="hint" style={{ margin: "12px 0" }}>Not classified yet — press <b>c</b> or click "Classify new".</div>}
            <div className="reply-bar">
              <button className="primary" disabled={replyBusy} onClick={() => onDraftReply(sel.thread_id)}>
                {replyBusy ? "Drafting…" : "Draft reply"}
              </button>
              <span className="hint">key <b>d</b> · saved as a Gmail draft (never sent)</span>
            </div>
            {reply && reply.thread_id === sel.thread_id && (
              <div className="reply">
                <div className="reply-meta">
                  To: {reply.to} · {reply.subject}
                  {reply.draft_id && <span className="badge">saved draft</span>}
                  <span className="badge">{reply.glean_used ? `Glean: ${reply.sources.length}` : "no Glean"}</span>
                </div>
                <textarea className="reply-text" defaultValue={reply.draft_text} rows={12} />
                {reply.sources.length > 0 && (
                  <div className="reply-sources">
                    {reply.sources.map((s, i) => (
                      <a key={i} href={s.url} target="_blank" rel="noreferrer" className="src">{s.title}</a>
                    ))}
                  </div>
                )}
              </div>
            )}
            <ThreadReader detail={detail} loading={detailLoading} />
          </>
        ) : (
          <div className="empty">Select a conversation (or use <b>j</b>/<b>k</b>) to read and adjust its labels.</div>
        )}
      </div>

      {showHelp && <ShortcutsModal onClose={() => setShowHelp(false)} />}
    </>
  );
}

function ThreadReader({ detail, loading }: { detail: ThreadDetail | null; loading: boolean }) {
  if (loading) return <div className="hint">Loading conversation…</div>;
  if (!detail) return null;
  return (
    <div className="thread">
      {detail.messages.map((m) => (
        <div key={m.message_id} className="msg">
          <div className="msg-head">
            <span className="msg-from">{displayName(m.from_addr)}</span>
            <span className="msg-date">{m.date_str}</span>
          </div>
          {m.body_html
            ? <HtmlBody html={m.body_html} />
            : <pre className="msg-body">{m.body_text || m.snippet}</pre>}
        </div>
      ))}
    </div>
  );
}

// Render a message's HTML safely (sanitized) in a sandboxed, auto-sized iframe
// so the email's own CSS can't leak into the app and scripts can't run.
function HtmlBody({ html }: { html: string }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const doc = useMemo(() => {
    const clean = DOMPurify.sanitize(html, { FORBID_TAGS: ["script", "style"], FORBID_ATTR: ["srcset"] });
    return `<!doctype html><html><head><base target="_blank"><meta charset="utf-8">` +
      `<style>html,body{margin:0;padding:2px 2px 0;font-family:-apple-system,system-ui,sans-serif;` +
      `font-size:13px;line-height:1.5;color:#23211c;word-break:break-word;}` +
      `img{max-width:100%;height:auto;}a{color:#b5512f;}table{max-width:100%;}</style></head>` +
      `<body>${clean}</body></html>`;
  }, [html]);
  function resize() {
    const f = ref.current;
    try {
      const h = f?.contentWindow?.document.body.scrollHeight;
      if (f && h) f.style.height = `${h + 16}px`;
    } catch { /* cross-origin guard */ }
  }
  return (
    <iframe ref={ref} className="msg-frame" sandbox="allow-same-origin allow-popups"
            srcDoc={doc} onLoad={resize} title="message" />
  );
}

function ShortcutsModal({ onClose }: { onClose: () => void }) {
  const rows: [string, string][] = [
    ["j / ↓", "Next conversation"],
    ["k / ↑", "Previous conversation"],
    ["s", "Sync inbox"],
    ["c", "Classify new"],
    ["1 / 2 / 3", "Status: Open / In Progress / Completed"],
    ["d", "Draft reply"],
    ["r", "Refresh"],
    ["?", "Toggle this help"],
  ];
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Keyboard shortcuts</h3>
        {rows.map(([k, d]) => (
          <div key={k} className="shortcut-row"><kbd>{k}</kbd><span>{d}</span></div>
        ))}
        <div className="actions"><button className="primary" onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}

// Dropdown editor for the 6 facets. Org gates which conditional facets apply.
function FacetEditor({ facets, tax, onSave }: {
  facets: Facets; tax: Taxonomy; onSave: (f: Facets) => Promise<void>;
}) {
  const [f, setF] = useState<Facets>(facets);
  const [saving, setSaving] = useState(false);
  useEffect(() => setF(facets), [facets]);

  async function save(next: Facets) {
    setSaving(true);
    try { await onSave(next); } finally { setSaving(false); }
  }

  function pick<K extends keyof Facets>(k: K, v: Facets[K]) {
    const next = { ...f, [k]: v };
    setF(next);
    save(next);
  }

  const dirty = JSON.stringify(f) !== JSON.stringify(facets);

  return (
    <div className="facets">
      <Select label="Type" value={f.type} options={tax.type} onChange={(v) => pick("type", v)} />
      <Select label="Org" value={f.org} options={tax.org} onChange={(v) => pick("org", v)} />
      <Select label="Prio" value={f.prio} options={tax.prio} onChange={(v) => pick("prio", v)} />
      {f.org === "Internal" && (
        <Select label="DBX" value={f.dbx ?? ""} options={["", ...tax.dbx]} onChange={(v) => pick("dbx", v || null)} />
      )}
      {f.org === "Customer" && (
        <>
          <Select label="Bosch" value={f.bosch ?? ""} options={["", ...tax.bosch]} onChange={(v) => pick("bosch", v || null)} />
          <MultiSelect label="BU" values={f.bu} options={tax.bu} onChange={(vs) => pick("bu", vs)} />
        </>
      )}
      {f.labels.length > 0 && <Chips labels={f.labels} />}
      {saving && <span className="hint">saving…</span>}
      {dirty && !saving && <span className="hint">unsaved</span>}
    </div>
  );
}

function Select({ label, value, options, onChange }: {
  label: string; value: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
      </select>
    </label>
  );
}

function MultiSelect({ label, values, options, onChange }: {
  label: string; values: string[]; options: string[]; onChange: (vs: string[]) => void;
}) {
  function toggle(o: string) {
    onChange(values.includes(o) ? values.filter((v) => v !== o) : [...values, o]);
  }
  return (
    <div className="field">
      <span>{label}</span>
      <div className="chips">
        {options.map((o) => (
          <span key={o} className={`chip cat-bu f ${values.includes(o) ? "on" : ""}`} onClick={() => toggle(o)}>{o}</span>
        ))}
      </div>
    </div>
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
