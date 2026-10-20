import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";

const VARIANTS: Record<string, "default" | "secondary" | "outline" | "success" | "warning" | "destructive" | "muted" | "info"> = {
  draft: "muted",
  in_review: "info",
  specified: "info",
  ready: "info",
  in_progress: "warning",
  verified: "success",
  verification_failed: "destructive",
  done: "success",
  rejected: "destructive",
  queued: "muted",
  running: "warning",
  paused: "muted",
  awaiting_merge: "info",
  failed: "destructive",
  cancelled: "muted",
  succeeded: "success",
  pending: "muted",
  skipped: "muted",
  success: "success",
  failure: "destructive",
  ok: "success",
  error: "destructive",
  off: "muted",
};

export function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const known = t(`status.${status}`, { defaultValue: "" });
  return (
    <Badge variant={VARIANTS[status] ?? "outline"}>{known || status}</Badge>
  );
}
