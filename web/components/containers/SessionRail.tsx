"use client";

import { Plus, UsersRound } from "lucide-react";
import { SESSION_STATUS_LABELS, sessionTone } from "@/lib/container-presentation";
import type { WorkSessionSummary } from "@/lib/types";

export function SessionRail({
  sessions,
  selectedId,
  onSelect,
  onAdd,
}: {
  sessions: WorkSessionSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
}) {
  return (
    <aside className="flex min-h-0 w-full flex-col border-r border-border bg-white/60" aria-label="Sessions">
      <div className="flex min-h-14 items-center justify-between border-b border-border px-5">
        <h2 className="text-sm font-semibold">Sessions</h2>
        <span className="font-mono text-xs text-muted-foreground">{sessions.length}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {sessions.map((session) => {
          const selected = session.id === selectedId;
          return (
            <button
              key={session.id}
              type="button"
              onClick={() => onSelect(session.id)}
              aria-pressed={selected}
              className={`relative w-full border-b border-border px-5 py-5 text-left transition-colors duration-fast ${
                selected ? "bg-accent/[0.055]" : "hover:bg-muted/45"
              }`}
            >
              {selected ? <span className="absolute inset-y-0 left-0 w-0.5 bg-accent" /> : null}
              <span className="flex items-start gap-3">
                <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${selected ? "border-accent/30 bg-accent/10 text-accent" : "border-border bg-white text-muted-foreground"}`}>
                  <UsersRound className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-foreground">{session.role}</span>
                    <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
                      <span className={`h-1.5 w-1.5 rounded-full ${sessionTone(session.status)}`} />
                      {SESSION_STATUS_LABELS[session.status] ?? session.status}
                    </span>
                  </span>
                  <span className="mt-1.5 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                    {session.goal}
                  </span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="flex min-h-14 items-center gap-2 border-t border-border px-5 text-sm font-semibold text-accent transition-colors hover:bg-accent/5"
      >
        <Plus className="h-4 w-4" />添加 Session
      </button>
    </aside>
  );
}
