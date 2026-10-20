import { Check, Copy } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { AgentEvent } from "@/api/types";
import { Button } from "@/components/ui/button";
import { useRunEvents } from "@/hooks/useRunEvents";
import { cn } from "@/lib/utils";

interface LogLine {
  key: string;
  kind: "system" | "tool" | "result" | "assistant" | "error" | "stdout";
  text: string;
}

function describe(event: AgentEvent, index: number): LogLine[] {
  const data = event.data as Record<string, any>;
  const key = `${event.seq ?? index}`;

  if (event.type === "system") {
    return [
      {
        key,
        kind: "system",
        text: `system/${data.subtype ?? "event"}${data.session_id ? ` session=${data.session_id}` : ""}`,
      },
    ];
  }

  if (event.type === "assistant") {
    const content = data?.message?.content;
    if (!Array.isArray(content)) return [];
    return content.flatMap((block: any, blockIndex: number): LogLine[] => {
      if (block?.type === "text" && block.text) {
        return [{ key: `${key}-${blockIndex}`, kind: "assistant" as const, text: block.text }];
      }
      if (block?.type === "tool_use") {
        const input = block.input ? JSON.stringify(block.input) : "";
        return [
          {
            key: `${key}-${blockIndex}`,
            kind: "tool" as const,
            text: `→ ${block.name ?? "tool"} ${input}`.trim(),
          },
        ];
      }
      return [];
    });
  }

  if (event.type === "user") {
    const content = data?.message?.content;
    if (!Array.isArray(content)) return [];
    return content.flatMap((block: any, blockIndex: number): LogLine[] => {
      if (block?.type === "tool_result") {
        const raw =
          typeof block.content === "string"
            ? block.content
            : Array.isArray(block.content)
              ? block.content.map((part: any) => part?.text ?? "").join(" ")
              : JSON.stringify(block.content ?? "");
        return [
          {
            key: `${key}-${blockIndex}`,
            kind: block.is_error ? ("error" as const) : ("result" as const),
            text: `← ${raw.slice(0, 4000)}`,
          },
        ];
      }
      if (block?.type === "text" && block.text) {
        return [{ key: `${key}-${blockIndex}`, kind: "assistant" as const, text: block.text }];
      }
      return [];
    });
  }

  if (event.type === "result") {
    return [
      {
        key,
        kind: data.is_error ? "error" : "result",
        text: `${data.subtype ?? "result"}${data.total_cost_usd != null ? ` cost=$${data.total_cost_usd}` : ""}\n${data.result ?? ""}`,
      },
    ];
  }

  if (event.type === "stdout") {
    return [{ key, kind: "stdout", text: String(data.text ?? "") }];
  }

  return [];
}

export function RunLog({ runId, className }: { runId: string | null; className?: string }) {
  const { t } = useTranslation();
  const { events, connected } = useRunEvents(runId);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copied, setCopied] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  const lines = useMemo(
    () => events.flatMap((event, index) => describe(event, index)),
    [events],
  );

  useEffect(() => {
    if (autoScroll) bottom.current?.scrollIntoView({ block: "end" });
  }, [lines.length, autoScroll]);

  const copy = async () => {
    await navigator.clipboard.writeText(lines.map((line) => line.text).join("\n"));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className={cn("flex min-h-0 flex-col overflow-hidden rounded-lg border bg-[oklch(0.13_0_0)]", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-3 py-2 text-xs text-zinc-300">
        <span className="flex items-center gap-2">
          <span className={cn("size-2 rounded-full", connected ? "bg-emerald-400" : "bg-zinc-500")} />
          {connected ? t("logs.waiting") : t("common.loading")}
        </span>
        <span className="flex items-center gap-1">
          <label className="flex cursor-pointer items-center gap-1">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(event) => setAutoScroll(event.target.checked)}
              className="size-3"
            />
            {t("logs.autoScroll")}
          </label>
          <Button variant="ghost" size="sm" className="text-zinc-300 hover:bg-white/10" onClick={() => void copy()}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            {copied ? t("logs.copied") : t("logs.copy")}
          </Button>
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3 font-mono text-[12px] leading-5">
        {lines.length === 0 ? (
          <div className="text-zinc-500">{t("logs.empty")}</div>
        ) : (
          lines.map((line) => (
            <div
              key={line.key}
              className={cn(
                "whitespace-pre-wrap break-words",
                line.kind === "tool" && "text-sky-300",
                line.kind === "result" && "text-emerald-300",
                line.kind === "error" && "text-red-300",
                line.kind === "system" && "text-zinc-500",
                line.kind === "assistant" && "text-zinc-100",
                line.kind === "stdout" && "text-zinc-300",
              )}
            >
              {line.text}
            </div>
          ))
        )}
        <div ref={bottom} />
      </div>
    </div>
  );
}
