import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, Search } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { api, Incident } from "../lib/api";
import { Command, filterCommands } from "../lib/commandSearch";
import { statusLabel } from "../lib/pipeline";

/**
 * Ctrl/Cmd+K command palette. Commands are supplied by the app shell; "Open investigation" entries are the user's
 * REAL investigations, fetched from the API each time the palette opens (none are listed if the request fails).
 *
 * Accessibility: modal dialog, labelled combobox + listbox with aria-activedescendant, focus is moved in on open,
 * trapped while open, and restored to the previously focused element on close. Esc closes.
 */
export default function CommandPalette({ open, onClose, commands, onOpenInvestigation }: {
  open: boolean; onClose: () => void; commands: Command[]; onOpenInvestigation: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const uid = useId();
  const listId = `${uid}-list`;

  useEffect(() => {
    if (!open) return;
    returnFocus.current = document.activeElement as HTMLElement | null;
    setQuery(""); setActive(0);
    let live = true;
    api.listIncidents().then((rows) => { if (live) setIncidents(rows.slice(0, 25)); }).catch(() => { if (live) setIncidents([]); });
    const t = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => { live = false; window.clearTimeout(t); returnFocus.current?.focus?.(); };
  }, [open]);

  const all = useMemo<Command[]>(() => [
    ...commands,
    ...incidents.map((i) => ({
      id: `inc-${i.id}`, group: "Investigations", label: i.title, hint: `${statusLabel(i.status)} · ${i.id.slice(0, 8).toUpperCase()}`,
      keywords: [i.id, i.id.slice(0, 8)], run: () => onOpenInvestigation(i.id),
    })),
  ], [commands, incidents, onOpenInvestigation]);
  const results = useMemo(() => filterCommands(all, query), [all, query]);
  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => { document.getElementById(`${uid}-opt-${active}`)?.scrollIntoView({ block: "nearest" }); }, [active, uid]);

  function run(c: Command | undefined) { if (!c) return; onClose(); window.setTimeout(c.run, 0); }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (results.length ? (a + 1) % results.length : 0)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (results.length ? (a - 1 + results.length) % results.length : 0)); }
    else if (e.key === "Home") { e.preventDefault(); setActive(0); }
    else if (e.key === "End") { e.preventDefault(); setActive(Math.max(0, results.length - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); run(results[active]); }
    else if (e.key === "Tab") {
      // The input is the only tab stop inside the dialog, so Tab stays put instead of leaving the modal.
      e.preventDefault(); inputRef.current?.focus();
    }
  }

  let lastGroup = "";
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[12vh] bg-black/40 backdrop-blur-[2px]"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}
          onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <motion.div
            ref={dialogRef} role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={onKeyDown}
            className="w-full max-w-[560px] rounded-2xl border border-border bg-card shadow-soft overflow-hidden"
            initial={{ opacity: 0, y: -12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }} transition={{ duration: 0.18 }}
          >
            <div className="flex items-center gap-3 px-4 border-b border-border">
              <Search size={16} className="text-faint shrink-0" aria-hidden="true" />
              <input
                ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)}
                role="combobox" aria-expanded="true" aria-controls={listId} aria-autocomplete="list"
                aria-activedescendant={results.length ? `${uid}-opt-${active}` : undefined}
                aria-label="Search commands and investigations"
                placeholder="Search screens, actions and investigations…"
                className="w-full h-12 bg-transparent text-[14px] text-ink outline-none placeholder:text-muted"
              />
              <kbd className="hidden sm:block text-[10px] text-muted border border-border rounded px-1.5 py-0.5">Esc</kbd>
            </div>
            {results.length === 0 && <p role="status" id={listId} className="px-4 py-6 text-center text-[13px] text-muted">No matching command or investigation.</p>}
            {results.length > 0 && <ul id={listId} role="listbox" aria-label="Results" className="max-h-[50vh] overflow-y-auto py-2">
              {results.map((c, i) => {
                const header = c.group !== lastGroup ? c.group : null;
                lastGroup = c.group;
                return (
                  <li key={c.id} role="presentation">
                    {header && !query && <p aria-hidden="true" className="px-4 pt-2 pb-1 text-[10.5px] tracking-[.12em] uppercase font-semibold text-muted">{header}</p>}
                    <div
                      id={`${uid}-opt-${i}`} role="option" aria-selected={i === active}
                      onMouseMove={() => setActive(i)} onClick={() => run(c)}
                      className={`mx-2 flex items-center justify-between gap-3 rounded-lg px-3 py-2 cursor-pointer ${i === active ? "bg-soft text-ink" : "text-ink"}`}
                    >
                      <span className="min-w-0">
                        <span className="block text-[13px] font-medium truncate">{c.label}</span>
                        {c.hint && <span className="block text-[11px] text-muted truncate">{c.hint}</span>}
                      </span>
                      {i === active && <CornerDownLeft size={13} className="text-muted shrink-0" aria-hidden="true" />}
                    </div>
                  </li>
                );
              })}
            </ul>}
            <div className="flex items-center justify-between px-4 py-2 border-t border-border text-[10.5px] text-muted">
              <span>↑↓ to move · Enter to run</span>
              <span>Opening an investigation loads it; nothing is changed by browsing.</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
