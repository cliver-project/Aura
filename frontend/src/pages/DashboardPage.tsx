import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, CheckCircle2, FolderGit2, PlaySquare, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { AgentRun, Health, Project } from "@/api/types";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";

export function DashboardPage() {
  const { t } = useTranslation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => (await api.get<Health>("/health")).data,
    refetchInterval: 15000,
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get<Project[]>("/projects")).data,
  });
  const runs = useQuery({
    queryKey: ["runs", "recent"],
    queryFn: async () => (await api.get<AgentRun[]>("/agent-runs", { params: { limit: 8 } })).data,
    refetchInterval: 5000,
  });

  const requirementCount = (projects.data ?? []).reduce(
    (sum, project) => sum + project.requirement_count,
    0,
  );
  const activeRuns = (runs.data ?? []).filter((run) =>
    ["queued", "running"].includes(run.status),
  ).length;
  const healthy = (health.data?.services ?? []).filter((service) => service.status === "ok").length;

  const stats = [
    { label: t("dashboard.statProjects"), value: projects.data?.length ?? 0, icon: FolderGit2 },
    { label: t("dashboard.statRequirements"), value: requirementCount, icon: CheckCircle2 },
    { label: t("dashboard.statRunning"), value: activeRuns, icon: PlaySquare },
    { label: t("dashboard.statServices"), value: `${healthy}/${health.data?.services.length ?? 0}`, icon: Bot },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{t("dashboard.title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("dashboard.subtitle")}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardContent className="flex items-center justify-between p-5">
              <div>
                <div className="text-sm text-muted-foreground">{label}</div>
                <div className="mt-1 text-2xl font-semibold">{value}</div>
              </div>
              <span className="flex size-10 items-center justify-center rounded-lg bg-muted">
                <Icon className="size-5" />
              </span>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>{t("dashboard.recentRuns")}</CardTitle>
              <CardDescription>{t("runs.subtitle")}</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/runs" className="flex items-center gap-1">
                {t("common.view")} <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {runs.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : (runs.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("dashboard.noRuns")}</p>
            ) : (
              <div className="divide-y">
                {(runs.data ?? []).map((run) => (
                  <div key={run.id} className="flex items-center gap-3 py-3 text-sm">
                    <StatusBadge status={run.status} />
                    <span className="font-mono text-xs text-muted-foreground">{run.stage}</span>
                    <span className="min-w-0 flex-1 truncate">{run.result_text || run.error || run.id}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{formatDate(run.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.services")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {health.isLoading ? (
                <Skeleton className="h-16 w-full" />
              ) : (
                (health.data?.services ?? []).map((service) => (
                  <div key={service.name} className="flex items-center justify-between gap-2 text-sm">
                    <div className="min-w-0">
                      <div className="font-medium capitalize">{service.name}</div>
                      <div className="truncate text-xs text-muted-foreground">{service.detail}</div>
                    </div>
                    <Badge
                      variant={
                        service.status === "ok"
                          ? "success"
                          : service.status === "off"
                            ? "muted"
                            : "destructive"
                      }
                    >
                      {service.status === "ok"
                        ? t("dashboard.serviceOk")
                        : service.status === "off"
                          ? t("dashboard.serviceOff")
                          : t("dashboard.serviceError")}
                    </Badge>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("dashboard.quickStart")}</CardTitle>
              <CardDescription>{t("dashboard.quickStartText")}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button asChild>
                <Link to="/projects" className="flex items-center gap-2">
                  <Plus className="size-4" /> {t("dashboard.createProject")}
                </Link>
              </Button>
              <Button variant="outline" asChild>
                <Link to="/projects">{t("dashboard.viewProjects")}</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
