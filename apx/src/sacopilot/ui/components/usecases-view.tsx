import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Uco, UcoDetail, listUcos, getUco, generateUco, updateUco } from "@/lib/cockpit-api";

const stageCls = (s: string) =>
  ({ U1: "bg-muted", U2: "bg-muted", U3: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
     U4: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
     U5: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300" } as Record<string, string>)[s] ?? "bg-muted";

// SFDC date (YYYY-MM-DD) -> DD/MM/YYYY for display.
function fmtDate(d: string | null): string {
  if (!d) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : d;
}

// Use-Case Quality; hover shows what's missing when below max.
function QualityBadge({ q, max, missing }: { q: number; max: number; missing: string[] }) {
  const cls = q >= max ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300"
    : q >= max - 2 ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
    : "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
  const tip = q >= max ? `Use-Case Quality ${max}/${max} — all checks pass`
    : "Missing (" + (max - q) + "):\n" + missing.map((m) => "• " + m).join("\n");
  return (
    <span className={`inline-block min-w-[34px] text-xs font-semibold px-2 py-0.5 rounded cursor-help ${cls}`} title={tip}>
      {q}/{max}
    </span>
  );
}

export function UseCasesView() {
  const [account, setAccount] = useState("Bosch Global");
  const [prefix, setPrefix] = useState("[NS]");
  const [ucos, setUcos] = useState<Uco[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [detail, setDetail] = useState<UcoDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [nsPrompt, setNsPrompt] = useState(""); const [nsGen, setNsGen] = useState(""); const [nsBusy, setNsBusy] = useState(false); const [nsFb, setNsFb] = useState("");
  const [obPrompt, setObPrompt] = useState(""); const [obGen, setObGen] = useState(""); const [obBusy, setObBusy] = useState(false); const [obFb, setObFb] = useState("");
  const [confirm, setConfirm] = useState(false); const [saving, setSaving] = useState(false);

  async function load() {
    setError(null); setLoading(true);
    try { setUcos(await listUcos(account, prefix)); }
    catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); /* initial */ }, []);
  useEffect(() => {
    setNsGen(""); setObGen(""); setNsPrompt(""); setObPrompt(""); setNsFb(""); setObFb("");
    if (!selId) { setDetail(null); return; }
    getUco(selId).then(setDetail).catch((e) => setError(String(e)));
  }, [selId]);

  async function gen(artifact: "next_steps" | "onboarding") {
    if (!selId) return;
    const setBusy = artifact === "next_steps" ? setNsBusy : setObBusy;
    const setGen = artifact === "next_steps" ? setNsGen : setObGen;
    const setFb = artifact === "next_steps" ? setNsFb : setObFb;
    const prompt = artifact === "next_steps" ? nsPrompt : obPrompt;
    setBusy(true); setError(null);
    try { const r = await generateUco(selId, artifact, prompt); setGen(r.text); setFb(r.feedback); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function doUpdate() {
    if (!selId) return;
    const fields: { next_steps?: string; onboarding?: string } = {};
    if (nsGen.trim()) fields.next_steps = nsGen;
    if (obGen.trim()) fields.onboarding = obGen;
    setConfirm(false); setSaving(true); setError(null);
    try {
      await updateUco(selId, fields);
      // reflect new values as the current content
      setDetail((d) => d && ({ ...d, next_steps: fields.next_steps ?? d.next_steps, onboarding: fields.onboarding ?? d.onboarding }));
      setNsGen(""); setObGen("");
    } catch (e) { setError(String(e)); }
    finally { setSaving(false); }
  }

  const sel = ucos.find((u) => u.id === selId) ?? null;
  const canUpdate = !!(nsGen.trim() || obGen.trim());

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Filter bar */}
      <div className="border-b p-3 flex gap-2 items-center flex-wrap">
        <label className="text-xs text-muted-foreground">Account</label>
        <input value={account} onChange={(e) => setAccount(e.target.value)}
          className="text-sm border rounded-md px-2 py-1 bg-background w-44" />
        <label className="text-xs text-muted-foreground ml-2">Name prefix</label>
        <input value={prefix} onChange={(e) => setPrefix(e.target.value)}
          className="text-sm border rounded-md px-2 py-1 bg-background w-28" />
        <Button size="sm" onClick={load} disabled={loading}>{loading ? "Loading…" : "Load"}</Button>
        <span className="text-xs text-muted-foreground ml-auto">{ucos.length} use-cases</span>
      </div>
      {error && <div className="px-4 py-2 text-sm text-destructive">{error}</div>}

      <div className="flex-1 min-h-0 overflow-auto">
        {/* Table */}
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted-foreground border-b sticky top-0 bg-background">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-2 py-2 w-12">Stage</th>
              <th className="px-2 py-2 w-16 text-center" title="Use-Case Quality (0–7)">Quality</th>
              <th className="px-2 py-2 w-24">NS updated</th>
              <th className="px-2 py-2 w-24">Onb. updated</th>
              <th className="px-2 py-2 w-24">Go-live</th>
              <th className="px-2 py-2 w-24">Onboarding</th>
              <th className="px-2 py-2 w-20">Status</th>
              <th className="px-2 py-2">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {ucos.map((u) => (
              <tr key={u.id} onClick={() => setSelId(u.id)}
                className={`border-b cursor-pointer hover:bg-muted/50 ${selId === u.id ? "bg-muted" : ""}`}>
                <td className="px-3 py-2">{u.name}</td>
                <td className="px-2 py-2"><span className={`text-[11px] px-1.5 py-0.5 rounded ${stageCls(u.stage)}`}>{u.stage}</span></td>
                <td className="px-2 py-2 text-center"><QualityBadge q={u.quality} max={u.quality_max} missing={u.quality_missing} /></td>
                <td className="px-2 py-2 text-muted-foreground whitespace-nowrap">{u.ns_update_date ?? "—"}</td>
                <td className="px-2 py-2 text-muted-foreground whitespace-nowrap">{u.ob_update_date ?? "—"}</td>
                <td className="px-2 py-2 text-muted-foreground whitespace-nowrap">{fmtDate(u.go_live_date)}</td>
                <td className="px-2 py-2 text-muted-foreground whitespace-nowrap">{fmtDate(u.onboarding_date)}</td>
                <td className="px-2 py-2 text-muted-foreground">{u.implementation_status ?? "—"}</td>
                <td className="px-2 py-2 text-muted-foreground">{u.implementation_strategy ?? "—"}</td>
              </tr>
            ))}
            {ucos.length === 0 && !loading && (
              <tr><td colSpan={9} className="px-3 py-8 text-center text-muted-foreground">No use-cases. Adjust the filter and Load.</td></tr>
            )}
          </tbody>
        </table>

        {/* Editor */}
        {sel && detail && (
          <div className="border-t p-4">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-base font-semibold">{detail.name}</h2>
              <span className={`text-[11px] px-1.5 py-0.5 rounded ${stageCls(detail.stage)}`}>{detail.stage}</span>
              <span className="text-xs text-muted-foreground">{detail.account}</span>
              <div className="ml-auto flex items-center gap-2">
                <Button size="sm" disabled={!canUpdate || saving} onClick={() => setConfirm(true)}>
                  {saving ? "Updating…" : "Update use-case"}
                </Button>
              </div>
            </div>

            <Artifact title="Next Steps" current={detail.next_steps}
              prompt={nsPrompt} setPrompt={setNsPrompt} gen={nsGen} setGen={setNsGen}
              feedback={nsFb} busy={nsBusy} onGenerate={() => gen("next_steps")} />

            <div className="h-5" />

            {detail.onboarding_allowed ? (
              <Artifact title="Onboarding Notes" current={detail.onboarding}
                prompt={obPrompt} setPrompt={setObPrompt} gen={obGen} setGen={setObGen}
                feedback={obFb} busy={obBusy} onGenerate={() => gen("onboarding")} />
            ) : (
              <div className="text-xs text-muted-foreground border rounded-md p-3">
                Onboarding Notes apply from stage U3 onward (this UCO is {detail.stage}).
              </div>
            )}
          </div>
        )}
      </div>

      {confirm && sel && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setConfirm(false)}>
          <div className="bg-card border rounded-xl p-5 w-[440px] shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-semibold mb-2">Update in Salesforce?</h3>
            <p className="text-sm text-muted-foreground">
              Write {[nsGen.trim() && "Next Steps", obGen.trim() && "Onboarding Notes"].filter(Boolean).join(" + ")} to <b>{sel.name}</b>.
            </p>
            <div className="flex gap-2 justify-end mt-4">
              <Button size="sm" variant="outline" onClick={() => setConfirm(false)}>Cancel</Button>
              <Button size="sm" onClick={doUpdate}>Update</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Artifact({ title, current, prompt, setPrompt, gen, setGen, feedback, busy, onGenerate }: {
  title: string; current: string; prompt: string; setPrompt: (v: string) => void;
  gen: string; setGen: (v: string) => void; feedback: string; busy: boolean; onGenerate: () => void;
}) {
  return (
    <section>
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Current (Salesforce)</div>
          <textarea readOnly value={current || "(empty)"} rows={14}
            className="w-full text-[12px] leading-relaxed border rounded-md p-2 bg-muted/30 resize-y font-mono" />
        </div>
        <div>
          <div className="flex gap-2 mb-1">
            <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="prompt changes…"
              className="flex-1 text-sm border rounded-md px-2 py-1 bg-background" />
            <Button size="sm" disabled={busy} onClick={onGenerate}>{busy ? "…" : "Generate"}</Button>
          </div>
          <textarea value={gen} onChange={(e) => setGen(e.target.value)} rows={13} placeholder="generated draft (editable)…"
            className="w-full text-[12px] leading-relaxed border rounded-md p-2 bg-background resize-y font-mono" />
          {feedback && (
            <div className="mt-2 border rounded-md p-2 bg-amber-50 dark:bg-amber-950/30">
              <div className="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-400 mb-1">Feedback — input needed / changes made</div>
              <pre className="text-[11px] whitespace-pre-wrap break-words leading-relaxed text-amber-900 dark:text-amber-200">{feedback}</pre>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
