import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, ScrollText, Square } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Agent, AgentRun } from "@/api/types";
import { RunLog } from "@/components/RunLog";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDuration } from "@/lib/utils";

export function RunsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [stageFilter, setStageFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<AgentRun | null>(null);

  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: async () => (await api.get<AgentRun[]>("/agent-runs", { params: { limit: 200 } })).data,
    refetchInterval: 5000,
  });
  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: async () => (await api.get<Agent[]>("/agents")).data,
  });

  const agentNames = useMemo(
    () => new Map((agents.data ?? []).map((agent) => [agent.id, agent.name])),
    [agents.data],
  );

  const cancel = useMutation({
    mutationFn: async (run: AgentRun) => api.post(`/agent-runs/${run.id}/cancel`),
    onSuccess: () => {
      toast.success(t("runs.cancel"));
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const filtered = (runs.data ?? []).filter(
    (run) =>
      (!stageFilter || run.stage === stageFilter) &&
      (!statusFilter || run.status === statusFilter),
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{t("runs.title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("runs.subtitle")}</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Select
          className="w-52"
          value={stageFilter}
          onChange={(event) => setStageFilter(event.target.value)}
        >
          <option value="">{t("runs.allStages")}</option>
          {["refine", "spec", "challenge", "consolidate", "implement", "verify", "code_review"].map(
            (stage) => (
              <option key={stage} value={stage}>
                {t(`stages.${stage}`)}
              </option>
            ),
          )}
        </Select>
        <Select
          className="w-44"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
        >
          <option value="">{t("common.all")}</option>
          {["queued", "running", "succeeded", "failed", "cancelled"].map((status) => (
            <option key={status} value={status}>
              {t(`status.${status}`)}
            </option>
          ))}
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("runs.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">{t("runs.empty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{t("runs.status")}</th>
                    <th className="py-2 pr-4 font-medium">{t("runs.stage")}</th>
                    <th className="py-2 pr-4 font-medium">{t("runs.agent")}</th>
                    <th className="py-2 pr-4 font-medium">{t("runs.started")}</th>
                    <th className="py-2 pr-4 font-medium">{t("runs.duration")}</th>
                    <th className="py-2 pr-4 font-medium">{t("runs.cost")}</th>
                    <th className="py-2 pr-4 font-medium">{t("runs.tokens")}</th>
                    <th className="py-2 font-medium">{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((run) => (
                    <tr key={run.id} className="border-b last:border-0">
                      <td className="py-3 pr-4">
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="py-3 pr-4">{t(`stages.${run.stage}`, { defaultValue: run.stage })}</td>
                      <td className="py-3 pr-4">
                        {run.agent_profile_id ? agentNames.get(run.agent_profile_id) ?? "-" : "-"}
                      </td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">
                        {formatDate(run.started_at ?? run.created_at)}
                      </td>
                      <td className="py-3 pr-4 text-xs">
                        {formatDuration(run.started_at, run.finished_at)}
                      </td>
                      <td className="py-3 pr-4 text-xs">
                        {run.cost_usd != null ? `$${run.cost_usd.toFixed(4)}` : "-"}
                      </td>
                      <td className="py-3 pr-4 text-xs">
                        {run.total_tokens ? run.total_tokens : "-"}
                      </td>
                      <td className="py-3">
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={() => setSelected(run)}>
                            <ScrollText className="size-3.5" /> {t("runs.viewLogs")}
                          </Button>
                          {run.requirement_id ? (
                            <Button variant="ghost" size="sm" asChild>
                              <Link to={`/requirements/${run.requirement_id}`}>
                                <ExternalLink className="size-3.5" /> {t("common.open")}
                              </Link>
                            </Button>
                          ) : null}
                          {run.status === "running" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => cancel.mutate(run)}
                            >
                              <Square className="size-3.5" /> {t("runs.cancel")}
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected ? `${t("runs.title")} · ${selected.stage}` : t("logs.title")}
        description={
          selected
            ? `${selected.id} · ${formatDate(selected.started_at ?? selected.created_at)}`
            : undefined
        }
        className="max-w-5xl"
      >
        {selected ? (
          <div className="space-y-4">
            <div className="grid gap-2 text-xs sm:grid-cols-2">
              <div>
                <span className="text-muted-foreground">{t("runs.workspace")}: </span>
                <span className="break-all font-mono">{selected.workspace || "-"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">{t("runs.cost")}: </span>
                {selected.cost_usd != null ? `$${selected.cost_usd.toFixed(4)}` : "-"}
                <span className="ml-4 text-muted-foreground">{t("runs.tokens")}: </span>
                {selected.total_tokens || "-"}
              </div>
              <div>
                <span className="text-muted-foreground">{t("runs.duration")}: </span>
                {formatDuration(selected.started_at, selected.finished_at)}
              </div>
              <div>
                <span className="text-muted-foreground">exit: </span>
                {selected.exit_code ?? "-"}
              </div>
            </div>
            {selected.error ? (
              <p className="whitespace-pre-wrap rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
                {selected.error}
              </p>
            ) : null}
            <RunLog runId={selected.id} className="h-[55vh]" />
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
