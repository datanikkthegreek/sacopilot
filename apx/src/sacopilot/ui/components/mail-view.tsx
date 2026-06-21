import { useEffect, useMemo, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { Button } from "@/components/ui/button";
import {
  Facets, Taxonomy, Thread, ThreadDetail, ThreadMessage, InboxCounts, ReplyDraft,
  listThreads, getThread, classifyMail, syncMail, getTaxonomy,
  updateClassification, setStatus, draftReply, sendReply,
} from "@/lib/cockpit-api";

// --- helpers ----------------------------------------------------------------
const categoryOf = (l: string) => l.split("/")[0];
const CATEGORY_ORDER = ["Type", "Org", "Prio", "DBX", "Bosch", "BU", "Needs"];
const STATUSES = ["Open", "In Progress", "Completed"] as const;
const displayName = (f: string) => f.replace(/<[^>]*>/, "").replace(/"/g, "").trim() || f;

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === new Date().toDateString()) return time;
  return `${d.toLocaleDateString([], { day: "2-digit", month: "2-digit" })} · ${time}`;
}

const CAT_CLASS: Record<string, string> = {
  Type: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  Org: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  Prio: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  DBX: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  Bosch: "bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
  BU: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
  Needs: "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-200",
};
const chipCls = (l: string) =>
  `text-[11px] px-2 py-0.5 rounded-md font-medium ${CAT_CLASS[categoryOf(l)] ?? "bg-muted text-muted-foreground"}`;
const STATUS_CLASS: Record<string, string> = {
  "In Progress": "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  Completed: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
};

function Chips({ labels }: { labels: string[] }) {
  return (
    <div className="flex gap-1 flex-wrap">
      {labels.map((l) => <span key={l} className={chipCls(l)}>{l}</span>)}
    </div>
  );
}

// --- mail -------------------------------------------------------------------
export function MailView() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [counts, setCounts] = useState<InboxCounts>({ total: 0, unread: 0, classified: 0 });
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [selId, setSelId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [filters, setFilters] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [tax, setTax] = useState<Taxonomy | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number; verb: string } | null>(null);
  const [reply, setReply] = useState<ReplyDraft | null>(null);
  const [replyBusy, setReplyBusy] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = progress !== null;

  const byCat = new Map<string, string[]>();
  filters.forEach((f) => byCat.set(categoryOf(f), [...(byCat.get(categoryOf(f)) ?? []), f]));
  const shown = threads.filter((t) =>
    [...byCat.values()].every((s) => s.some((f) => t.labels.includes(f))));
  const present = Array.from(new Set(threads.flatMap((t) => t.labels)));
  const groups = CATEGORY_ORDER
    .map((c) => [c, present.filter((l) => categoryOf(l) === c).sort()] as const)
    .filter(([, ls]) => ls.length > 0);
  const sel = threads.find((t) => t.thread_id === selId) ?? null;

  async function refresh(opts?: { unread?: boolean; status?: string | null }) {
    const unread = opts?.unread ?? unreadOnly;
    const status = opts?.status === undefined ? statusFilter : opts.status;
    setError(null);
    try {
      const page = await listThreads(0, { unread, status: status ?? undefined });
      setThreads(page.threads); setCounts(page.counts);
      setOffset(page.threads.length); setHasMore(page.has_more);
    } catch (e) { setError(String(e)); }
  }
  async function loadOlder() {
    try {
      const page = await listThreads(offset, { unread: unreadOnly, status: statusFilter ?? undefined });
      setThreads((prev) => {
        const seen = new Set(prev.map((t) => t.thread_id));
        return [...prev, ...page.threads.filter((t) => !seen.has(t.thread_id))];
      });
      setOffset((o) => o + page.threads.length); setHasMore(page.has_more);
    } catch (e) { setError(String(e)); }
  }

  useEffect(() => { refresh(); getTaxonomy().then(setTax).catch(() => {}); }, []);
  useEffect(() => {
    setReply(null);
    if (!selId) { setDetail(null); return; }
    setDetailLoading(true);
    getThread(selId).then(setDetail).catch((e) => setError(String(e))).finally(() => setDetailLoading(false));
  }, [selId]);

  function move(delta: number) {
    if (!shown.length) return;
    const i = shown.findIndex((t) => t.thread_id === selId);
    const n = i < 0 ? 0 : Math.min(shown.length - 1, Math.max(0, i + delta));
    setSelId(shown[n].thread_id);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (el && ["INPUT", "SELECT", "TEXTAREA"].includes(el.tagName)) return;
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "s" && !busy) syncNow();
      else if (e.key === "c" && !busy) classifyNew();
      else if (e.key === "r") refresh();
      else if (selId && e.key === "1") onStatus(selId, "Open");
      else if (selId && e.key === "2") onStatus(selId, "In Progress");
      else if (selId && e.key === "3") onStatus(selId, "Completed");
      else if (selId && e.key === "d" && !replyBusy) onDraftReply(selId);
      else if (e.key === "?") setShowHelp((s) => !s);
      else if (e.key === "Escape") { setShowHelp(false); setConfirmSend(false); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function toggleFilter(label: string) {
    const next = new Set(filters);
    next.has(label) ? next.delete(label) : next.add(label);
    setFilters(next);
  }
  function toggleUnread() { const v = !unreadOnly; setUnreadOnly(v); refresh({ unread: v }); }
  function pickStatusFilter(s: string) {
    const v = statusFilter === s ? null : s;
    setStatusFilter(v); refresh({ status: v });
  }

  async function syncNow() {
    setError(null); setProgress({ done: 0, total: 0, verb: "synced" });
    try {
      await syncMail((e) => {
        if (e.type === "start") setProgress({ done: 0, total: e.total, verb: "synced" });
        else if (e.type === "progress") setProgress({ done: e.done, total: e.total, verb: "synced" });
        else if (e.type === "item_error") setProgress((p) => p && { ...p, done: e.done, total: e.total });
        else if (e.type === "error") setError(e.message);
      });
    } catch (err) { setError(String(err)); }
    finally { setProgress(null); refresh(); }
  }
  async function classifyNew() {
    setError(null); setProgress({ done: 0, total: 0, verb: "classified" });
    try {
      await classifyMail((e) => {
        if (e.type === "start") setProgress({ done: 0, total: e.total, verb: "classified" });
        else if (e.type === "progress") {
          setProgress({ done: e.done, total: e.total, verb: "classified" });
          setThreads((ts) => ts.map((t) => t.thread_id === e.thread_id
            ? { ...t, classified: true, adjusted: false, labels: e.labels, facets: e.facets } : t));
        } else if (e.type === "item_error") setProgress((p) => p && { ...p, done: e.done, total: e.total });
        else if (e.type === "error") setError(e.message);
      });
    } catch (err) { setError(String(err)); }
    finally { setProgress(null); }
  }
  async function onEdit(threadId: string, facets: Facets) {
    const { labels } = await updateClassification(threadId, facets);
    const merged = { ...facets, labels };
    setThreads((ts) => ts.map((t) => t.thread_id === threadId ? { ...t, labels, adjusted: true, facets: merged } : t));
    setDetail((d) => (d && d.thread_id === threadId ? { ...d, facets: merged } : d));
  }
  async function onStatus(threadId: string, status: string) {
    try {
      const res = await setStatus(threadId, status);
      if (res.archived) {
        const idx = shown.findIndex((t) => t.thread_id === threadId);
        const next = shown[idx + 1]?.thread_id ?? shown[idx - 1]?.thread_id ?? null;
        setThreads((ts) => ts.filter((t) => t.thread_id !== threadId));
        setCounts((c) => ({ ...c, total: Math.max(0, c.total - 1) }));
        if (selId === threadId) setSelId(next);
      } else {
        setThreads((ts) => ts.map((t) => t.thread_id === threadId ? { ...t, status } : t));
      }
    } catch (e) { setError(String(e)); }
  }
  async function onDraftReply(threadId: string) {
    setReplyBusy(true); setError(null);
    try { setReply(await draftReply(threadId)); } catch (e) { setError(String(e)); }
    finally { setReplyBusy(false); }
  }
  async function doSend() {
    if (!reply || !sel) return;
    const box = document.getElementById("reply-box") as HTMLTextAreaElement | null;
    const body = box?.value ?? reply.draft_text;
    const latest = detail?.messages[detail.messages.length - 1];
    setConfirmSend(false); setReplyBusy(true); setError(null);
    try {
      await sendReply(sel.thread_id, {
        to: reply.to, subject: reply.subject, body,
        reply_to_message_id: latest?.message_id ?? null, draft_id: reply.draft_id,
      });
      setReply(null);
      refresh();
    } catch (e) { setError(String(e)); }
    finally { setReplyBusy(false); }
  }

  return (
    <div className="flex h-full min-h-0">
      {/* List pane */}
      <div className="w-[38%] min-w-[340px] border-r overflow-y-auto">
        <div className="sticky top-0 z-10 bg-background border-b p-3 flex gap-2 items-center flex-wrap">
          <Button size="sm" disabled={busy} onClick={syncNow}>
            {busy && progress?.verb === "synced" ? "Syncing…" : "Sync"}
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={classifyNew}>
            {busy && progress?.verb === "classified" ? "Classifying…" : "Classify new"}
          </Button>
          <Button size="sm" variant={unreadOnly ? "default" : "outline"} onClick={toggleUnread}>Unread</Button>
          <span className="text-xs text-muted-foreground ml-auto">
            {counts.total} · {counts.unread} unread · {counts.classified} classified
          </span>
          <button className="text-[11px] text-muted-foreground hover:text-foreground" onClick={() => setShowHelp(true)}>? keys</button>
        </div>

        {progress && (
          <div className="px-4 py-2 border-b">
            <div className="h-1.5 bg-muted rounded overflow-hidden">
              <div className="h-full bg-primary transition-[width] duration-300"
                style={{ width: progress.total ? `${(progress.done / progress.total) * 100}%` : "0%" }} />
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">
              {progress.total === 0
                ? (progress.verb === "synced" ? "Scanning inbox…" : "Finding unclassified…")
                : `${progress.done} / ${progress.total} ${progress.verb}`}
            </div>
          </div>
        )}

        <div className="px-4 py-2 border-b flex flex-col gap-1.5">
          <div className="flex items-center gap-1 flex-wrap">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground w-11 shrink-0">Status</span>
            {STATUSES.map((s) => (
              <button key={s} onClick={() => pickStatusFilter(s)}
                className={`text-[11px] px-2 py-0.5 rounded-md ${statusFilter === s ? "bg-primary text-primary-foreground" : STATUS_CLASS[s] ?? "bg-muted text-muted-foreground"}`}>
                {s}
              </button>
            ))}
          </div>
          {groups.map(([cat, labels]) => (
            <div key={cat} className="flex items-center gap-1 flex-wrap">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground w-11 shrink-0">{cat}</span>
              {labels.map((l) => (
                <button key={l} onClick={() => toggleFilter(l)}
                  className={`text-[11px] px-2 py-0.5 rounded-md ${filters.has(l) ? "bg-primary text-primary-foreground" : chipCls(l)}`}>
                  {l.includes("/") ? l.split("/")[1] : l}
                </button>
              ))}
            </div>
          ))}
        </div>

        {error && <div className="p-4 text-sm text-destructive">{error}</div>}
        {shown.map((t) => (
          <div key={t.thread_id} onClick={() => setSelId(t.thread_id)}
            className={`px-4 py-2.5 border-b cursor-pointer transition-colors hover:bg-muted/50 ${
              selId === t.thread_id ? "bg-muted shadow-[inset_3px_0_0] shadow-primary" : ""}`}>
            <div className={`flex items-center text-[13px] ${t.unread ? "font-bold" : "font-semibold"}`}>
              {t.unread && <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary mr-1.5" />}
              <span className="truncate">{displayName(t.from)}</span>
              {t.message_count > 1 && <span className="ml-1.5 text-[10px] bg-muted rounded-full px-1.5 text-muted-foreground">{t.message_count}</span>}
              <span className="ml-auto pl-2 text-[11px] font-normal text-muted-foreground shrink-0">{fmtDate(t.date)}</span>
            </div>
            <div className={`text-[13px] truncate ${t.unread ? "font-semibold" : ""}`}>{t.subject}</div>
            <div className="text-xs text-muted-foreground truncate">{t.snippet}</div>
            <div className="flex gap-1 flex-wrap items-center mt-1">
              {t.status !== "Open" && <span className={`text-[11px] px-2 py-0.5 rounded-md ${STATUS_CLASS[t.status] ?? ""}`}>{t.status}</span>}
              {t.adjusted && <span className="text-[10px] text-muted-foreground">edited</span>}
              {t.labels.length > 0 && <Chips labels={t.labels} />}
            </div>
          </div>
        ))}
        {threads.length === 0 && !error && (
          <div className="p-9 text-center text-sm text-muted-foreground">Inbox not synced — click <b>Sync</b> (or press <b>s</b>).</div>
        )}
        {shown.length === 0 && threads.length > 0 && <div className="p-9 text-center text-sm text-muted-foreground">No matches.</div>}
        {hasMore && shown.length > 0 && (
          <div className="p-3 text-center"><Button size="sm" variant="outline" onClick={loadOlder}>Load older</Button></div>
        )}
      </div>

      {/* Reading pane */}
      <div className="flex-1 overflow-y-auto p-6">
        {sel ? (
          <>
            <h2 className="text-lg font-semibold tracking-tight">{sel.subject}</h2>
            <div className="flex gap-1.5 items-center my-3">
              {STATUSES.map((s) => (
                <button key={s} onClick={() => onStatus(sel.thread_id, s)}
                  className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                    sel.status === s ? (STATUS_CLASS[s] ?? "bg-muted") : "text-muted-foreground hover:bg-muted/60"}`}>
                  {s}
                </button>
              ))}
              <span className="text-[11px] text-muted-foreground ml-1">keys 1/2/3</span>
            </div>

            {sel.facets && tax
              ? <FacetEditor key={sel.thread_id} facets={sel.facets} tax={tax} onSave={(f) => onEdit(sel.thread_id, f)} />
              : <div className="text-[11px] text-muted-foreground my-3">Not classified yet — press <b>c</b>.</div>}

            <div className="flex items-center gap-2.5 my-3">
              <Button size="sm" disabled={replyBusy} onClick={() => onDraftReply(sel.thread_id)}>
                {replyBusy ? "Working…" : "Draft reply"}
              </Button>
              {reply && reply.thread_id === sel.thread_id && (
                <Button size="sm" variant="destructive" disabled={replyBusy} onClick={() => setConfirmSend(true)}>Send…</Button>
              )}
              <span className="text-[11px] text-muted-foreground">key <b>d</b> · draft never auto-sends</span>
            </div>

            {reply && reply.thread_id === sel.thread_id && (
              <div className="border rounded-lg p-3 mb-4 bg-card">
                <div className="text-xs text-muted-foreground flex items-center gap-2 flex-wrap mb-2">
                  To: {reply.to} · {reply.subject}
                  {reply.draft_id && <span className="text-[10px] bg-muted rounded px-1.5">saved draft</span>}
                  <span className="text-[10px] bg-muted rounded px-1.5">{reply.glean_used ? `Glean: ${reply.sources.length}` : "no Glean"}</span>
                </div>
                <textarea id="reply-box" defaultValue={reply.draft_text} rows={12}
                  className="w-full text-[13px] leading-relaxed border rounded-md p-2.5 bg-background resize-y" />
                {reply.sources.length > 0 && (
                  <div className="flex gap-2 flex-wrap mt-2">
                    {reply.sources.map((s, i) => (
                      <a key={i} href={s.url} target="_blank" rel="noreferrer"
                        className="text-[11px] text-primary bg-muted px-2 py-0.5 rounded">{s.title}</a>
                    ))}
                  </div>
                )}
              </div>
            )}

            <ThreadReader detail={detail} loading={detailLoading} />
          </>
        ) : (
          <div className="p-9 text-center text-sm text-muted-foreground">Select a conversation (or <b>j</b>/<b>k</b>).</div>
        )}
      </div>

      {showHelp && <ShortcutsModal onClose={() => setShowHelp(false)} />}
      {confirmSend && reply && (
        <ConfirmModal
          title="Send this reply?"
          body={`This will SEND the email to ${reply.to}. This cannot be undone.`}
          confirmLabel="Send"
          onCancel={() => setConfirmSend(false)}
          onConfirm={doSend} />
      )}
    </div>
  );
}

// --- reading pane -----------------------------------------------------------
function ThreadReader({ detail, loading }: { detail: ThreadDetail | null; loading: boolean }) {
  if (loading) return <div className="text-[11px] text-muted-foreground">Loading conversation…</div>;
  if (!detail) return null;
  const msgs = [...detail.messages].reverse(); // newest on top
  return (
    <div className="mt-4 border-t">
      {msgs.map((m) => <MessageBlock key={m.message_id} m={m} />)}
    </div>
  );
}

function MessageBlock({ m }: { m: ThreadMessage }) {
  return (
    <div className="py-3.5 border-b">
      <div className="flex justify-between gap-2.5 text-xs mb-2">
        <span className="font-semibold">{displayName(m.from_addr)}</span>
        <span className="text-muted-foreground whitespace-nowrap">{m.date_str}</span>
      </div>
      {m.body_html
        ? <HtmlBody html={m.body_html} />
        : <pre className="whitespace-pre-wrap break-words text-[13px] leading-relaxed m-0 max-w-[74ch]">{m.body_text || m.snippet}</pre>}
    </div>
  );
}

function HtmlBody({ html }: { html: string }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const doc = useMemo(() => {
    const clean = DOMPurify.sanitize(html, { FORBID_TAGS: ["script", "style"], FORBID_ATTR: ["srcset"] });
    return `<!doctype html><html><head><base target="_blank"><meta charset="utf-8">` +
      `<style>html,body{margin:0;padding:2px;font-family:-apple-system,system-ui,sans-serif;font-size:13px;line-height:1.5;color:#18181b;word-break:break-word;}img{max-width:100%;height:auto;}a{color:#b5512f;}table{max-width:100%;}</style></head><body>${clean}</body></html>`;
  }, [html]);
  function resize() {
    const f = ref.current;
    try { const h = f?.contentWindow?.document.body.scrollHeight; if (f && h) f.style.height = `${h + 16}px`; } catch { /* */ }
  }
  return <iframe ref={ref} sandbox="allow-same-origin allow-popups" srcDoc={doc} onLoad={resize}
    title="message" className="w-full border-0 bg-white min-h-[40px]" />;
}

// --- facet editor -----------------------------------------------------------
function FacetEditor({ facets, tax, onSave }: { facets: Facets; tax: Taxonomy; onSave: (f: Facets) => Promise<void> }) {
  const [f, setF] = useState<Facets>(facets);
  const [saving, setSaving] = useState(false);
  useEffect(() => setF(facets), [facets]);
  function pick<K extends keyof Facets>(k: K, v: Facets[K]) {
    const next = { ...f, [k]: v }; setF(next);
    setSaving(true); onSave(next).finally(() => setSaving(false));
  }
  return (
    <div className="flex flex-col gap-2.5 my-3.5 p-3.5 border rounded-lg bg-card">
      <Sel label="Type" value={f.type} options={tax.type} onChange={(v) => pick("type", v)} />
      <Sel label="Org" value={f.org} options={tax.org} onChange={(v) => pick("org", v)} />
      <Sel label="Prio" value={f.prio} options={tax.prio} onChange={(v) => pick("prio", v)} />
      {f.org === "Internal" && <Sel label="DBX" value={f.dbx ?? ""} options={["", ...tax.dbx]} onChange={(v) => pick("dbx", v || null)} />}
      {f.org === "Customer" && <>
        <Sel label="Bosch" value={f.bosch ?? ""} options={["", ...tax.bosch]} onChange={(v) => pick("bosch", v || null)} />
        <Multi label="BU" values={f.bu} options={tax.bu} onChange={(vs) => pick("bu", vs)} />
      </>}
      {f.labels.length > 0 && <Chips labels={f.labels} />}
      {saving && <span className="text-[11px] text-muted-foreground">saving…</span>}
    </div>
  );
}
function Sel({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="flex items-center gap-2.5 text-[13px]">
      <span className="w-14 text-muted-foreground shrink-0">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 border rounded-md bg-background text-[13px]">
        {options.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
      </select>
    </label>
  );
}
function Multi({ label, values, options, onChange }: { label: string; values: string[]; options: string[]; onChange: (vs: string[]) => void }) {
  const toggle = (o: string) => onChange(values.includes(o) ? values.filter((v) => v !== o) : [...values, o]);
  return (
    <div className="flex items-start gap-2.5 text-[13px]">
      <span className="w-14 text-muted-foreground shrink-0 pt-1">{label}</span>
      <div className="flex gap-1 flex-wrap">
        {options.map((o) => (
          <button key={o} onClick={() => toggle(o)}
            className={`text-[11px] px-2 py-0.5 rounded-md ${values.includes(o) ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>{o}</button>
        ))}
      </div>
    </div>
  );
}

// --- modals -----------------------------------------------------------------
function ConfirmModal({ title, body, confirmLabel, onConfirm, onCancel }:
  { title: string; body: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-card border rounded-xl p-5 w-[420px] shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground">{body}</p>
        <div className="flex gap-2 justify-end mt-4">
          <Button size="sm" variant="outline" onClick={onCancel}>Cancel</Button>
          <Button size="sm" variant="destructive" onClick={onConfirm}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}
function ShortcutsModal({ onClose }: { onClose: () => void }) {
  const rows: [string, string][] = [
    ["j / ↓", "Next"], ["k / ↑", "Previous"], ["s", "Sync inbox"], ["c", "Classify new"],
    ["1 / 2 / 3", "Status Open / In Progress / Completed"], ["d", "Draft reply"], ["r", "Refresh"], ["?", "This help"],
  ];
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-card border rounded-xl p-5 w-[440px] shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold mb-3">Keyboard shortcuts</h3>
        {rows.map(([k, d]) => (
          <div key={k} className="flex items-center gap-3 py-1 text-sm">
            <kbd className="bg-muted border rounded px-2 py-0.5 text-xs min-w-[64px] text-center">{k}</kbd>
            <span>{d}</span>
          </div>
        ))}
        <div className="flex justify-end mt-4"><Button size="sm" onClick={onClose}>Close</Button></div>
      </div>
    </div>
  );
}

