import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Todo, BoardMeta, TodoInput, listTodos, boardMeta, createTodo, updateTodo, deleteTodo } from "@/lib/cockpit-api";

const PRIO_CLS: Record<string, string> = {
  "0": "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  "1": "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  "2": "bg-muted text-muted-foreground",
};
const chip = "text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground";

export function BoardView() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [meta, setMeta] = useState<BoardMeta | null>(null);
  const [editing, setEditing] = useState<Todo | "new" | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    listTodos().then(setTodos).catch((e) => setError(String(e)));
  }
  useEffect(() => { reload(); boardMeta().then(setMeta).catch(() => {}); }, []);

  const statuses = meta?.statuses ?? ["Open", "This week", "Next week", "In progress", "Completed"];

  async function onDrop(status: string) {
    const id = dragId; setDragId(null);
    if (!id) return;
    const t = todos.find((x) => x.id === id);
    if (!t || t.status === status) return;
    setTodos((ts) => ts.map((x) => x.id === id ? { ...x, status } : x)); // optimistic
    try { await updateTodo(id, { status }); } catch (e) { setError(String(e)); reload(); }
  }

  async function onDelete(id: string) {
    setEditing(null);
    try { await deleteTodo(id); setTodos((ts) => ts.filter((x) => x.id !== id)); }
    catch (e) { setError(String(e)); }
  }

  async function onSave(fields: TodoInput, id?: string) {
    try {
      if (id) { const u = await updateTodo(id, fields); setTodos((ts) => ts.map((x) => x.id === id ? u : x)); }
      else { const c = await createTodo(fields); setTodos((ts) => [c, ...ts]); }
      setEditing(null);
    } catch (e) { setError(String(e)); }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="border-b p-3 flex items-center gap-3">
        <Button size="sm" onClick={() => setEditing("new")}>+ Add card</Button>
        <span className="text-xs text-muted-foreground">{todos.length} cards</span>
        {error && <span className="text-xs text-destructive ml-2">{error}</span>}
      </div>

      <div className="flex-1 min-h-0 overflow-x-auto">
        <div className="flex gap-3 p-3 h-full" style={{ minWidth: "max-content" }}>
          {statuses.map((s) => {
            const cards = todos.filter((t) => t.status === s);
            return (
              <div key={s} className="w-72 shrink-0 flex flex-col bg-muted/30 rounded-lg border"
                onDragOver={(e) => e.preventDefault()} onDrop={() => onDrop(s)}>
                <div className="px-3 py-2 text-xs font-semibold flex items-center justify-between border-b">
                  <span>{s}</span><span className="text-muted-foreground">{cards.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
                  {cards.map((t) => (
                    <div key={t.id} draggable onDragStart={() => setDragId(t.id)}
                      onClick={() => setEditing(t)}
                      className="bg-card border rounded-md p-2.5 cursor-pointer hover:shadow-sm">
                      <div className="flex items-start gap-2">
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${PRIO_CLS[t.priority] ?? PRIO_CLS["2"]}`}>P{t.priority}</span>
                        <span className="text-[13px] flex-1">{t.title}</span>
                        {t.estimate_hours != null && <span className="text-[10px] text-muted-foreground whitespace-nowrap">~{t.estimate_hours}h</span>}
                      </div>
                      <div className="flex gap-1 flex-wrap mt-1.5">
                        {t.type && <span className={chip}>{t.type}</span>}
                        {t.use_case_name && <span className={chip}>UC: {t.use_case_name.replace(/^\[NS\]\s*/, "").slice(0, 22)}</span>}
                        {t.bu && <span className={chip}>BU/{t.bu}</span>}
                        {t.project && <span className={chip}>{t.project}</span>}
                        {t.tags.map((g) => <span key={g} className={chip}>#{g}</span>)}
                      </div>
                    </div>
                  ))}
                  {cards.length === 0 && <div className="text-[11px] text-muted-foreground text-center py-4">—</div>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {editing && meta && (
        <CardEditor todo={editing === "new" ? null : editing} meta={meta}
          onClose={() => setEditing(null)} onSave={onSave} onDelete={onDelete} />
      )}
    </div>
  );
}

function CardEditor({ todo, meta, onClose, onSave, onDelete }: {
  todo: Todo | null; meta: BoardMeta;
  onClose: () => void; onSave: (f: TodoInput, id?: string) => void; onDelete: (id: string) => void;
}) {
  const [f, setF] = useState<TodoInput>(todo ?? { status: "Open", priority: "2", tags: [] });
  const [tagText, setTagText] = useState((todo?.tags ?? []).join(", "));
  function set<K extends keyof TodoInput>(k: K, v: TodoInput[K]) { setF((p) => ({ ...p, [k]: v })); }

  function save() {
    const tags = tagText.split(",").map((s) => s.trim()).filter(Boolean);
    onSave({ ...f, tags, title: f.title || "(untitled)" }, todo?.id);
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-card border rounded-xl p-5 w-[520px] max-h-[85vh] overflow-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold mb-3">{todo ? "Edit card" : "New card"}</h3>
        <div className="flex flex-col gap-2.5 text-sm">
          <input autoFocus placeholder="Title" value={f.title ?? ""} onChange={(e) => set("title", e.target.value)}
            className="border rounded-md px-2 py-1.5 bg-background" />
          <textarea placeholder="Description (optional)" rows={2} value={f.description ?? ""} onChange={(e) => set("description", e.target.value)}
            className="border rounded-md px-2 py-1.5 bg-background resize-y" />
          <div className="grid grid-cols-3 gap-2">
            <Field label="Column"><Sel value={f.status ?? "Open"} opts={meta.statuses} onChange={(v) => set("status", v)} /></Field>
            <Field label="Priority"><Sel value={f.priority ?? "2"} opts={meta.priorities} fmt={(p) => "P" + p} onChange={(v) => set("priority", v)} /></Field>
            <Field label="Est. (h)"><input type="number" step="0.5" min="0" value={f.estimate_hours ?? ""} onChange={(e) => set("estimate_hours", e.target.value === "" ? null : Number(e.target.value))} className="w-full border rounded-md px-2 py-1 bg-background" /></Field>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Type"><Sel value={f.type ?? ""} opts={["", ...meta.types]} onChange={(v) => set("type", v || null)} /></Field>
            <Field label="BU"><Sel value={f.bu ?? ""} opts={["", ...meta.bu]} onChange={(v) => set("bu", v || null)} /></Field>
          </div>
          <Field label="Use-Case">
            <select value={f.use_case_id ?? ""}
              onChange={(e) => { const u = meta.use_cases.find((x) => x.id === e.target.value); set("use_case_id", u?.id ?? null); set("use_case_name", u?.name ?? null); }}
              className="w-full border rounded-md px-2 py-1 bg-background">
              <option value="">—</option>
              {meta.use_cases.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </Field>
          <Field label="Project"><input value={f.project ?? ""} onChange={(e) => set("project", e.target.value || null)} className="w-full border rounded-md px-2 py-1 bg-background" /></Field>
          <Field label="Tags"><input placeholder="comma, separated" value={tagText} onChange={(e) => setTagText(e.target.value)} className="w-full border rounded-md px-2 py-1 bg-background" /></Field>
        </div>
        <div className="flex gap-2 justify-between mt-4">
          {todo ? <Button size="sm" variant="destructive" onClick={() => onDelete(todo.id)}>Delete</Button> : <span />}
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={onClose}>Cancel</Button>
            <Button size="sm" onClick={save}>{todo ? "Save" : "Create"}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
function Sel({ value, opts, onChange, fmt }: { value: string; opts: string[]; onChange: (v: string) => void; fmt?: (v: string) => string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full border rounded-md px-2 py-1 bg-background">
      {opts.map((o) => <option key={o} value={o}>{o === "" ? "—" : fmt ? fmt(o) : o}</option>)}
    </select>
  );
}
