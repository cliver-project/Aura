import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CirclePlay,
  ExternalLink,
  GitMerge,
  ScrollText,
  Square,
  XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/api/client";
import type {
  AgentRun,
  Artifact,
  PipelineRun,
  Project,
  Requirement,
  RequirementVersion,
} from "@/api/types";
import { Markdown } from "@/components/Markdown";
import { RunLog } from "@/components/RunLog";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Modal } from "@/components/ui/modal";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { formatDate, formatDuration } from "@/lib/utils";

const STAGES = [
  "refine",
  "spec",
  "challenge",
  "consolidate",
  "implement",
  "verify",
  "code_review",
] as const;

export function RequirementDetailPage() {
  const { t } = useTranslation();
  const { requirementId } = useParams<{ requirementId: string }>();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [logRunId, setLogRunId] = useState<string | null>(null);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const requirement = useQuery({
    queryKey: ["requirement", requirementId],
    queryFn: async () => (await api.get<Requirement>(`/requirements/${requirementId}`)).data,
    enabled: Boolean(requirementId),
    refetchInterval: 5000,
  });

  const project = useQuery({
    queryKey: ["project", requirement.data?.project_id],
    queryFn: async () => (await api.get<Project>(`/projects/${requirement.data?.project_id}`)).data,
    enabled: Boolean(requirement.data?.project_id),
  });

  const versions = useQuery({
    queryKey: ["versions", requirementId],
    queryFn: async () =>
      (await api.get<RequirementVersion[]>(`/requirements/${requirementId}/versions`)).data,
    enabled: Boolean(requirementId),
  });

  const artifacts = useQuery({
    queryKey: ["artifacts", requirementId],
    queryFn: async () =>
      (await api.get<Artifact[]>(`/requirements/${requirementId}/artifacts`)).data,
    enabled: Boolean(requirementId),
  });

  const pipelines = useQuery({
    queryKey: ["pipeline-runs", requirementId],
    queryFn: async () =>
      (await api.get<PipelineRun[]>(`/requirements/${requirementId}/pipeline-runs`)).data,
    enabled: Boolean(requirementId),
    refetchInterval: 4000,
  });

  const runs = useQuery({
    queryKey: ["runs", requirementId],
    queryFn: async () =>
      (
        await api.get<AgentRun[]>("/agent-runs", {
          params: { requirement_id: requirementId, limit: 100 },
        })
      ).data,
    enabled: Boolean(requirementId),
    refetchInterval: 4000,
  });

  const latest = pipelines.data?.[0];
  const awaiting =
    pipelines.data?.find((pipeline) => pipeline.status === "awaiting_merge") ?? null;
  const activePipeline =
    pipelines.data?.find((pipeline) => ["queued", "running"].includes(pipeline.status)) ?? null;
  const delivered = requirement.data?.status === "done";
  const deliveredPipeline =
    pipelines.data?.find(
      (pipeline) => pipeline.status === "done" && pipeline.current_stage === "awaiting_merge",
    ) ?? null;
  // A later single-stage run (for example a retried verify) must not hide the
  // full pipeline that is waiting for the human merge decision. For a
  // delivered requirement, show the merged pipeline rather than a later
  // cancelled attempt.
  const shownPipeline = awaiting ?? (delivered ? (deliveredPipeline ?? latest) : latest);
  const active = Boolean(activePipeline);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["pipeline-runs", requirementId] });
    void queryClient.invalidateQueries({ queryKey: ["runs", requirementId] });
    void queryClient.invalidateQueries({ queryKey: ["requirement", requirementId] });
    void queryClient.invalidateQueries({ queryKey: ["artifacts", requirementId] });
    void queryClient.invalidateQueries({ queryKey: ["versions", requirementId] });
  };

  const startPipeline = useMutation({
    mutationFn: async (input: { startStage?: string | null; auto: boolean }) =>
      (
        await api.post<PipelineRun>(`/requirements/${requirementId}/pipeline`, {
          start_stage: input.startStage ?? null,
          auto: input.auto,
        })
      ).data,
    onSuccess: () => {
      toast.success(t("requirement.runFull"));
      refresh();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const cancelPipeline = useMutation({
    mutationFn: async () => api.post(`/pipeline-runs/${activePipeline?.id}/cancel`),
    onSuccess: () => {
      toast.success(t("requirement.cancelPipeline"));
      refresh();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const mergePipeline = useMutation({
    mutationFn: async () => api.post(`/pipeline-runs/${awaiting?.id}/merge`),
    onSuccess: () => {
      toast.success(t("requirement.mergePr"));
      setMergeOpen(false);
      refresh();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const rejectPipeline = useMutation({
    mutationFn: async () =>
      api.post(`/pipeline-runs/${awaiting?.id}/reject`, { reason: rejectReason }),
    onSuccess: () => {
      toast.success(t("requirement.reject"));
      setRejectOpen(false);
      refresh();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const runsByStage = useMemo(() => {
    const map = new Map<string, AgentRun[]>();
    for (const run of runs.data ?? []) {
      const list = map.get(run.stage) ?? [];
      list.push(run);
      map.set(run.stage, list);
    }
    return map;
  }, [runs.data]);

  if (requirement.isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!requirement.data) {
    return <p className="text-sm text-muted-foreground">{t("errors.notFound")}</p>;
  }

  const currentVersion = versions.data?.[0];
  const stageMap = new Map((shownPipeline?.stages ?? []).map((stage) => [stage.stage, stage]));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/projects/${requirement.data.project_id}`} className="flex items-center gap-1">
            <ArrowLeft className="size-4" /> {t("common.back")}
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">{requirement.data.key}</span>
            <StatusBadge status={requirement.data.status} />
            <span className="text-xs text-muted-foreground">v{requirement.data.current_version}</span>
          </div>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">{requirement.data.title}</h2>
          <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
            <span>
              {t("common.createdAt")}: {formatDate(requirement.data.created_at)}
            </span>
            {project.data ? (
              <a
                className="inline-flex items-center gap-1 hover:underline"
                href={project.data.repo_url}
                target="_blank"
                rel="noreferrer"
              >
                {t("requirement.repository")} <ExternalLink className="size-3" />
              </a>
            ) : null}
            {requirement.data.pr_url ? (
              <a
                className="inline-flex items-center gap-1 hover:underline"
                href={requirement.data.pr_url}
                target="_blank"
                rel="noreferrer"
              >
                {t("requirement.pullRequest")} #{requirement.data.pr_number}{" "}
                <ExternalLink className="size-3" />
              </a>
            ) : null}
          </div>
          {delivered ? (
            <p className="mt-2 text-xs text-muted-foreground">{t("requirement.deliveredHint")}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          {delivered ? (
            <Badge variant="success">{t("requirement.delivered")}</Badge>
          ) : (
            <Button
              disabled={active || Boolean(awaiting) || startPipeline.isPending}
              onClick={() => startPipeline.mutate({ auto: true })}
            >
              <CirclePlay className="size-4" /> {t("requirement.runFull")}
            </Button>
          )}
          {active ? (
            <Button variant="outline" onClick={() => cancelPipeline.mutate()}>
              <Square className="size-4" /> {t("requirement.cancelPipeline")}
            </Button>
          ) : null}
          {awaiting ? (
            <>
              <Button onClick={() => setMergeOpen(true)}>
                <GitMerge className="size-4" /> {t("requirement.mergePr")}
              </Button>
              <Button variant="outline" onClick={() => setRejectOpen(true)}>
                <XCircle className="size-4" /> {t("requirement.reject")}
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "overview", label: t("requirement.tabs.overview") },
          { value: "pipeline", label: t("requirement.tabs.pipeline") },
          { value: "artifacts", label: t("requirement.tabs.artifacts") },
          { value: "links", label: t("requirement.tabs.links") },
        ]}
      />

      {tab === "overview" ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>{t("requirement.currentVersion")}</CardTitle>
              <CardDescription>
                {currentVersion
                  ? `v${currentVersion.version} · ${currentVersion.source} · ${formatDate(currentVersion.created_at)}`
                  : t("requirement.noVersions")}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {versions.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : currentVersion ? (
                <Markdown content={currentVersion.content_md} />
              ) : (
                <p className="whitespace-pre-wrap text-sm">{requirement.data.initial_idea}</p>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{t("requirement.initialIdea")}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {requirement.data.initial_idea}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{t("requirement.versionHistory")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(versions.data ?? []).length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("requirement.noVersions")}</p>
                ) : (
                  (versions.data ?? []).map((version) => (
                    <details key={version.id} className="rounded-md border p-3">
                      <summary className="cursor-pointer text-sm font-medium">
                        v{version.version} · {version.source} · {formatDate(version.created_at)}
                      </summary>
                      <div className="mt-3">
                        {version.git_commit ? (
                          <div className="mb-2 font-mono text-xs text-muted-foreground">
                            {version.git_commit.slice(0, 12)}
                          </div>
                        ) : null}
                        <Markdown content={version.content_md} />
                      </div>
                    </details>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}

      {tab === "pipeline" ? (
        <div className="space-y-6">
          {awaiting ? (
            <Card className="border-blue-500/40 bg-blue-500/5">
              <CardHeader>
                <CardTitle>{t("requirement.awaitingMerge")}</CardTitle>
                <CardDescription>{t("requirement.awaitingMergeHint")}</CardDescription>
              </CardHeader>
            </Card>
          ) : null}
          {shownPipeline?.status === "failed" && shownPipeline.error ? (
            <Card className="border-destructive/40 bg-destructive/5">
              <CardHeader>
                <CardTitle>{t("requirement.pipelineFailed")}</CardTitle>
                <CardDescription className="whitespace-pre-wrap">
                  {shownPipeline.error}
                </CardDescription>
              </CardHeader>
            </Card>
          ) : null}

          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>{t("requirement.pipeline")}</CardTitle>
                <CardDescription>
                  {shownPipeline
                    ? `${t(`status.${shownPipeline.status}`, { defaultValue: shownPipeline.status })} · ${formatDate(shownPipeline.created_at)} · ${t("requirement.totalCost", { cost: shownPipeline.total_cost_usd.toFixed(4) })}`
                    : t("requirement.noPipeline")}
                </CardDescription>
              </div>
              {shownPipeline ? <StatusBadge status={shownPipeline.status} /> : null}
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {STAGES.map((stage, index) => {
                  const stageRun = stageMap.get(stage);
                  const stageRuns = runsByStage.get(stage) ?? [];
                  const run = stageRuns[0];
                  return (
                    <div key={stage} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="flex size-6 items-center justify-center rounded-full bg-muted text-xs font-medium">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 font-medium">{t(`stages.${stage}`)}</span>
                        <StatusBadge status={stageRun?.status ?? "pending"} />
                        {!delivered ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={active || Boolean(awaiting) || startPipeline.isPending}
                            onClick={() =>
                              startPipeline.mutate({ startStage: stage, auto: false })
                            }
                          >
                            {t("requirement.runStage")}
                          </Button>
                        ) : null}
                        {run ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setLogRunId(run.id)}
                          >
                            <ScrollText className="size-3.5" /> {t("requirement.viewLogs")}
                          </Button>
                        ) : null}
                      </div>
                      {stageRun ? (
                        <div className="mt-2 space-y-1 pl-8 text-xs text-muted-foreground">
                          <div className="flex flex-wrap gap-3">
                            {stageRuns.length > 1 ? (
                              <span>{stageRuns.length} agents</span>
                            ) : null}
                            {stageRun.started_at ? (
                              <span>
                                {t("requirement.duration")}:{" "}
                                {formatDuration(stageRun.started_at, stageRun.finished_at)}
                              </span>
                            ) : null}
                            {stageRun.cost_usd != null ? (
                              <span>
                                {t("requirement.cost")}: ${stageRun.cost_usd.toFixed(4)}
                              </span>
                            ) : null}
                            <span>
                              {t("requirement.tokens")}: {stageRun.total_tokens}
                            </span>
                            {run?.exit_code != null ? <span>exit {run.exit_code}</span> : null}
                          </div>
                          {stageRun.summary ? <p>{stageRun.summary}</p> : null}
                          {stageRun.error ? (
                            <p className="whitespace-pre-wrap text-destructive">{stageRun.error}</p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {tab === "artifacts" ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("requirement.tabs.artifacts")}</CardTitle>
            <CardDescription>{t("requirement.artifactsEmpty")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {artifacts.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (artifacts.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("requirement.artifactsEmpty")}</p>
            ) : (
              (artifacts.data ?? []).map((artifact) => (
                <details key={artifact.id} className="rounded-lg border p-4">
                  <summary className="cursor-pointer">
                    <span className="font-medium">{artifact.title || artifact.kind}</span>
                    <span className="ml-2 font-mono text-xs text-muted-foreground">
                      {artifact.path}
                    </span>
                  </summary>
                  <Separator className="my-3" />
                  <Markdown content={artifact.content} />
                </details>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}

      {tab === "links" ? (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>{t("requirement.repository")}</CardTitle>
            </CardHeader>
            <CardContent>
              {project.data ? (
                <a className="text-sm text-blue-600 hover:underline dark:text-blue-400" href={project.data.repo_url} target="_blank" rel="noreferrer">
                  {project.data.repo_owner}/{project.data.repo_name}
                </a>
              ) : (
                "-"
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("requirement.pullRequest")}</CardTitle>
            </CardHeader>
            <CardContent>
              {requirement.data.pr_url ? (
                <a className="text-sm text-blue-600 hover:underline dark:text-blue-400" href={requirement.data.pr_url} target="_blank" rel="noreferrer">
                  #{requirement.data.pr_number}
                </a>
              ) : (
                <span className="text-sm text-muted-foreground">-</span>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("requirement.ciStatus")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {requirement.data.ci_status ? (
                <StatusBadge status={requirement.data.ci_status} />
              ) : (
                <span className="text-sm text-muted-foreground">-</span>
              )}
              {requirement.data.ci_target_url ? (
                <a
                  className="block text-sm text-blue-600 hover:underline dark:text-blue-400"
                  href={requirement.data.ci_target_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("requirement.viewLogs")}
                </a>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Modal
        open={Boolean(logRunId)}
        onClose={() => setLogRunId(null)}
        title={t("logs.title")}
        className="max-w-4xl"
      >
        <RunLog runId={logRunId} className="h-[60vh]" />
      </Modal>

      <Modal
        open={mergeOpen}
        onClose={() => setMergeOpen(false)}
        title={t("requirement.mergeConfirmTitle")}
        description={t("requirement.mergeConfirmText")}
        footer={
          <>
            <Button variant="outline" onClick={() => setMergeOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={mergePipeline.isPending} onClick={() => mergePipeline.mutate()}>
              {mergePipeline.isPending ? t("common.loading") : t("requirement.confirmMerge")}
            </Button>
          </>
        }
      >
        <div className="space-y-2 text-sm">
          <div>
            <span className="text-muted-foreground">{t("requirement.pullRequest")}: </span>
            {requirement.data.pr_url ? (
              <a className="text-blue-600 hover:underline dark:text-blue-400" href={requirement.data.pr_url} target="_blank" rel="noreferrer">
                #{requirement.data.pr_number}
              </a>
            ) : (
              "-"
            )}
          </div>
          <div>
            <span className="text-muted-foreground">{t("requirement.ciStatus")}: </span>
            {requirement.data.ci_status ?? "-"}
          </div>
        </div>
      </Modal>

      <Modal
        open={rejectOpen}
        onClose={() => setRejectOpen(false)}
        title={t("requirement.rejectTitle")}
        footer={
          <>
            <Button variant="outline" onClick={() => setRejectOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={rejectPipeline.isPending}
              onClick={() => rejectPipeline.mutate()}
            >
              {t("requirement.confirmReject")}
            </Button>
          </>
        }
      >
        <Textarea
          value={rejectReason}
          placeholder={t("requirement.rejectReasonPlaceholder")}
          onChange={(event) => setRejectReason(event.target.value)}
        />
      </Modal>
    </div>
  );
}
