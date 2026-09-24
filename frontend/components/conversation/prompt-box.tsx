"use client";

import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { formatDate } from "@/lib/geo";
import { cn } from "@/lib/utils";
import { SCENE_SET } from "@/lib/vocabulary";
import { Button, Kbd, Tag } from "@/components/ui/primitives";
import type { SceneSet } from "@/components/workspace/store";

export const PROMPT_ID = "prompt-input";

// Short enough to stay on one line in the 360 px column.
const PLACEHOLDER = {
  single: "Ask about this scene…",
  bitemporal: "Ask about these two dates…",
  optical_sar: "Ask about this optical + SAR pair…",
} as const;

/** Only questions the scene set can actually run — this is what keeps routing off impossible tasks. */
function suggestionsFor(set: SceneSet): string[] {
  if (set.kind === "bitemporal") return ["What changed between these dates, and where?", "Detect building changes"];
  if (set.kind === "optical_sar") return ["Use optical and SAR together to show the water", "Identify built-up regions from radar and optical"];
  if (set.scenes[0].metadata.modality === "sar") return ["Find water in this SAR image", "Describe this satellite image"];
  return ["Describe this scene", "Calculate the water index for this region", "Analyze the vegetation health"];
}

export function scopeText(set: SceneSet): string {
  const dates = set.scenes.map((s) => formatDate(s.metadata.acquired_at));
  const label = SCENE_SET[set.kind].label;
  if (set.kind === "bitemporal" && dates.every(Boolean)) return `${label} · ${dates[0]} → ${dates[1]}`;
  if (set.kind === "optical_sar") return `${label} · ${dates.filter(Boolean).join(" / ") || set.title}`;
  return `${label} · ${dates[0] ?? set.scenes[0].metadata.filename}`;
}

export function PromptBox({
  set,
  hasAnalyses,
  running,
  disabledReason,
  onAsk,
  onStop,
}: {
  set: SceneSet | null;
  hasAnalyses: boolean;
  running: boolean;
  disabledReason: string | null;
  onAsk: (q: string) => void;
  onStop: () => void;
}) {
  const [draft, setDraft] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // A new scene set: pre-fill a sample's suggested question and put the cursor in the box.
  useEffect(() => {
    if (!set) return;
    const prefill = !hasAnalyses && set.suggestedQuestion;
    if (prefill) setDraft(set.suggestedQuestion!);
    // Select a pre-filled question so Enter accepts it and typing replaces it (never appends to it).
    requestAnimationFrame(() => {
      ref.current?.focus();
      if (prefill) ref.current?.select();
    });
  }, [set?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [draft]);

  const send = (q = draft) => {
    if (!q.trim() || running || disabledReason) return;
    onAsk(q);
    setDraft("");
  };

  const suggestions = set && !hasAnalyses && !draft.trim() ? suggestionsFor(set) : [];

  return (
    <div className="flex flex-col gap-2 border-t border-line bg-panel p-3">
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label="Suggested questions">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="rounded-full border border-line px-2.5 py-1 text-sm text-fg-muted transition-colors hover:border-line-strong hover:text-fg"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className={cn(
          "flex flex-col rounded-md border bg-base transition-colors focus-within:border-accent",
          set ? "border-line-strong" : "border-line",
        )}
      >
        <div className="flex items-center gap-2 px-3 pt-2">
          {set ? (
            <Tag tone="neutral" className="max-w-full">
              <span className="text-fg-faint">Scene set:</span>
              <span className="truncate text-fg">{scopeText(set)}</span>
            </Tag>
          ) : (
            <span className="text-xs text-fg-faint">No scenes yet</span>
          )}
        </div>
        <label htmlFor={PROMPT_ID} className="sr-only">
          Your question
        </label>
        <textarea
          id={PROMPT_ID}
          ref={ref}
          rows={1}
          value={draft}
          disabled={!set}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={set ? PLACEHOLDER[set.kind] : "Add images to ask a question"}
          className="min-h-11 resize-none bg-transparent px-3 py-2.5 text-base text-fg outline-none placeholder:text-fg-faint disabled:cursor-not-allowed"
        />
        <div className="flex items-center gap-2 px-2 pb-2">
          <span className="truncate pl-1 text-xs text-fg-faint">
            {disabledReason ?? (
              <>
                <Kbd>Enter</Kbd> to ask · <Kbd>Shift</Kbd>+<Kbd>Enter</Kbd> new line
              </>
            )}
          </span>
          {running ? (
            <Button type="button" size="sm" variant="danger" className="ml-auto" onClick={onStop} title="Stop (Esc)">
              <Square className="fill-current" /> Stop
            </Button>
          ) : (
            <Button type="submit" size="sm" variant="primary" className="ml-auto" disabled={!set || !draft.trim() || !!disabledReason}>
              Ask <ArrowUp />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
