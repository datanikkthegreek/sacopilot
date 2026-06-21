import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { CalEvent, getWeek } from "@/lib/cockpit-api";

// Google Calendar event-color palette (colorId -> hex). null -> default blue.
const GCAL: Record<string, string> = {
  "1": "#7986CB", "2": "#33B679", "3": "#8E24AA", "4": "#E67C73", "5": "#F6BF26",
  "6": "#F4511E", "7": "#039BE5", "8": "#616161", "9": "#3F51B5", "10": "#0B8043", "11": "#D50000",
};
const GNAME: Record<string, string> = {
  "1": "Lavender", "2": "Sage", "3": "Grape", "4": "Flamingo", "5": "Banana", "6": "Tangerine",
  "7": "Peacock", "8": "Graphite", "9": "Blueberry", "10": "Basil", "11": "Tomato", "": "Uncategorised",
};
// User's calendar categories (by Google colorId).
const CAT_NAME: Record<string, string> = {
  "5": "Private",            // Banana
  "10": "Databricks Internal", // Basil
  "9": "Customer Internal",  // Blueberry
  "6": "Customer External",  // Tangerine
  "3": "Preps",              // Grape
};
const catLabel = (c: string) => CAT_NAME[c] ?? GNAME[c] ?? `Color ${c}`;
const key = (id: string | null) => id ?? "";
const colorFor = (id: string | null) => GCAL[id ?? ""] ?? "#039BE5";

const DAY_START = 7, DAY_END = 20, HOUR_PX = 44;
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"];

const isoDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const hhmm = (d: Date) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const displayName = (f: string) => f.replace(/<[^>]*>/, "").replace(/"/g, "").trim() || f;

function mondayOf(d: Date): Date {
  const m = new Date(d);
  m.setDate(m.getDate() - ((m.getDay() + 6) % 7));
  m.setHours(0, 0, 0, 0);
  return m;
}

export function MeetingsView() {
  const [monday, setMonday] = useState<Date>(() => mondayOf(new Date()));
  const [events, setEvents] = useState<CalEvent[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [sel, setSel] = useState<CalEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true); setError(null);
    getWeek(isoDay(monday))
      .then((w) => setEvents(w.events))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [monday]);

  const days = Array.from({ length: 5 }, (_, i) => {
    const d = new Date(monday); d.setDate(d.getDate() + i); return d;
  });
  const friday = days[4];

  // Categories present this week (by colorId), with counts.
  const catCounts = new Map<string, number>();
  for (const e of events) catCounts.set(key(e.color_id), (catCounts.get(key(e.color_id)) ?? 0) + 1);
  const cats = [...catCounts.keys()].sort((a, b) => catLabel(a).localeCompare(catLabel(b)));

  const shown = events.filter((e) => !hidden.has(key(e.color_id)));

  const timed: CalEvent[][] = [[], [], [], [], []];
  const allDay: CalEvent[][] = [[], [], [], [], []];
  for (const e of shown) {
    if (!e.start) continue;
    const sd = new Date(e.start);
    const idx = Math.round((new Date(isoDay(sd)).getTime() - new Date(isoDay(monday)).getTime()) / 86400000);
    if (idx < 0 || idx > 4) continue;
    (e.all_day ? allDay : timed)[idx].push(e);
  }

  function shift(weeks: number) { const m = new Date(monday); m.setDate(m.getDate() + weeks * 7); setMonday(m); }
  function toggleCat(c: string) {
    const next = new Set(hidden); next.has(c) ? next.delete(c) : next.add(c); setHidden(next);
  }

  const hours = Array.from({ length: DAY_END - DAY_START }, (_, i) => DAY_START + i);
  const gridH = (DAY_END - DAY_START) * HOUR_PX;
  const fmtRange = `${monday.toLocaleDateString([], { day: "2-digit", month: "short" })} – ${friday.toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" })}`;

  return (
    <div className="flex h-full min-h-0">
      {/* Left: list view */}
      <div className="w-[34%] min-w-[300px] border-r overflow-y-auto">
        <div className="sticky top-0 bg-background border-b p-3 text-sm font-semibold">This work week</div>
        {error && <div className="p-4 text-sm text-destructive">{error}</div>}
        {days.map((d, i) => {
          const evs = [...timed[i]].sort((a, b) => (a.start > b.start ? 1 : -1)); // timed only; all-day shown in the grid strip
          return (
            <div key={i} className="border-b">
              <div className="px-3 py-1.5 text-[11px] uppercase tracking-wide text-muted-foreground bg-muted/40">
                {DAY_NAMES[i]} {d.toLocaleDateString([], { day: "2-digit", month: "2-digit" })}
              </div>
              {evs.length === 0 && <div className="px-3 py-2 text-xs text-muted-foreground">—</div>}
              {evs.map((e) => (
                <div key={e.id} className="px-3 py-1.5 flex gap-2 items-start cursor-pointer hover:bg-muted/50" onClick={() => setSel(e)}>
                  <span className="mt-1 w-2 h-2 rounded-full shrink-0" style={{ background: colorFor(e.color_id) }} />
                  <div className="min-w-0">
                    <div className="text-[13px] truncate">{e.summary}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {e.all_day ? "all day" : `${hhmm(new Date(e.start))}–${hhmm(new Date(e.end))}`}
                      {e.attendees.length > 0 && ` · ${e.attendees.length} guests`}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {/* Right: week grid */}
      <div className="flex-1 overflow-auto">
        <div className="sticky top-0 z-10 bg-background border-b p-3 flex items-center gap-2 flex-wrap">
          <Button size="sm" variant="outline" onClick={() => shift(-1)}>‹ Prev</Button>
          <Button size="sm" variant="outline" onClick={() => setMonday(mondayOf(new Date()))}>Today</Button>
          <Button size="sm" variant="outline" onClick={() => shift(1)}>Next ›</Button>
          <span className="text-sm font-medium ml-2">{fmtRange}</span>
          {loading && <span className="text-[11px] text-muted-foreground ml-2">loading…</span>}
        </div>

        {/* Category (color) filter */}
        {cats.length > 0 && (
          <div className="border-b px-3 py-2 flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-1">Categories</span>
            {cats.map((c) => {
              const off = hidden.has(c);
              return (
                <button key={c} onClick={() => toggleCat(c)}
                  className={`flex items-center gap-1.5 text-[11px] rounded-full border px-2 py-0.5 transition-opacity ${off ? "opacity-40" : ""}`}>
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: colorFor(c || null) }} />
                  {catLabel(c)}
                  <span className="text-muted-foreground">{catCounts.get(c)}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Day headers + all-day strip */}
        <div className="grid border-b" style={{ gridTemplateColumns: `48px repeat(5, 1fr)` }}>
          <div className="border-r" />
          {days.map((d, i) => (
            <div key={i} className="border-r px-2 py-1.5 text-center">
              <div className="text-xs font-semibold">{DAY_NAMES[i]}</div>
              <div className="text-[11px] text-muted-foreground">{d.toLocaleDateString([], { day: "2-digit", month: "2-digit" })}</div>
              <div className="flex flex-col gap-0.5 mt-1">
                {allDay[i].map((e) => (
                  <div key={e.id} className="text-[10px] rounded px-1 py-0.5 truncate text-white cursor-pointer"
                    style={{ background: colorFor(e.color_id) }} title={e.summary} onClick={() => setSel(e)}>{e.summary}</div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Time grid */}
        <div className="grid" style={{ gridTemplateColumns: `48px repeat(5, 1fr)` }}>
          <div className="relative" style={{ height: gridH }}>
            {hours.map((h) => (
              <div key={h} className="absolute right-1 text-[10px] text-muted-foreground -translate-y-1/2"
                style={{ top: (h - DAY_START) * HOUR_PX }}>{h}:00</div>
            ))}
          </div>
          {days.map((_, i) => (
            <div key={i} className="relative border-r"
              style={{ height: gridH, backgroundImage: `repeating-linear-gradient(var(--border) 0 1px, transparent 1px ${HOUR_PX}px)` }}>
              {timed[i].map((e) => {
                const s = new Date(e.start), en = new Date(e.end);
                const top = (s.getHours() + s.getMinutes() / 60 - DAY_START) * HOUR_PX;
                const h = Math.max(16, (en.getTime() - s.getTime()) / 3600000 * HOUR_PX);
                return (
                  <div key={e.id} className="absolute left-0.5 right-0.5 rounded px-1 py-0.5 overflow-hidden text-white cursor-pointer"
                    style={{ top, height: h, background: colorFor(e.color_id), borderLeft: `3px solid rgba(0,0,0,0.25)` }}
                    title={e.summary} onClick={() => setSel(e)}>
                    <div className="text-[10px] leading-tight font-medium truncate">{e.summary}</div>
                    <div className="text-[9px] leading-tight opacity-90">{hhmm(s)}</div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {sel && <EventDetail event={sel} onClose={() => setSel(null)} />}
    </div>
  );
}

function EventDetail({ event, onClose }: { event: CalEvent; onClose: () => void }) {
  const s = new Date(event.start), en = new Date(event.end);
  const when = event.all_day
    ? `${s.toLocaleDateString([], { weekday: "long", day: "2-digit", month: "long" })} · all day`
    : `${s.toLocaleDateString([], { weekday: "long", day: "2-digit", month: "long" })} · ${hhmm(s)}–${hhmm(en)}`;
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-card border rounded-xl p-5 w-[520px] max-h-[80vh] overflow-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-2">
          <span className="mt-1.5 w-3 h-3 rounded-full shrink-0" style={{ background: colorFor(event.color_id) }} />
          <h3 className="font-semibold text-base flex-1">{event.summary}</h3>
        </div>
        <div className="text-sm text-muted-foreground mt-1">{when}</div>
        {event.location && <div className="text-sm mt-2"><span className="text-muted-foreground">Location: </span>{event.location}</div>}
        {event.hangout && (
          <a href={event.hangout} target="_blank" rel="noreferrer"
            className="inline-block text-sm text-primary mt-2 underline">Join video call</a>
        )}
        {event.attendees.length > 0 && (
          <div className="mt-3">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">
              Participants ({event.attendees.length})
            </div>
            <div className="flex flex-col gap-1 max-h-48 overflow-auto">
              {event.attendees.map((a) => (
                <div key={a.email} className="flex items-center gap-2 text-sm">
                  <span className="w-1.5 h-1.5 rounded-full" title={a.status ?? ""}
                    style={{ background: a.status === "accepted" ? "#16a34a" : a.status === "declined" ? "#dc2626" : a.status === "tentative" ? "#f6bf26" : "#9ca3af" }} />
                  <span className="truncate">{displayName(a.name)}</span>
                  {a.organizer && <span className="text-[10px] bg-muted rounded px-1 text-muted-foreground">organizer</span>}
                  {a.optional && <span className="text-[10px] text-muted-foreground">optional</span>}
                </div>
              ))}
            </div>
          </div>
        )}
        {event.description && (
          <div className="mt-3">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">Details</div>
            <pre className="text-[12px] whitespace-pre-wrap break-words leading-relaxed max-h-56 overflow-auto">{event.description}</pre>
          </div>
        )}
        <div className="flex justify-end mt-4"><Button size="sm" onClick={onClose}>Close</Button></div>
      </div>
    </div>
  );
}
