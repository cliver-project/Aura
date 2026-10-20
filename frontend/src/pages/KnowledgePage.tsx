import { useQuery } from "@tanstack/react-query";
import { BookOpen, ExternalLink, RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import type { KnowledgeStatus } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type Dataset = Record<string, unknown>;

function text(value: unknown): string {
  return value == null ? "" : String(value);
}

export function KnowledgePage() {
  const { t } = useTranslation();
  const status = useQuery({
    queryKey: ["knowledge-status"],
    queryFn: async () => (await api.get<KnowledgeStatus>("/knowledge/status")).data,
    refetchInterval: 10000,
  });
  const datasets = useQuery({
    queryKey: ["knowledge-datasets", status.data?.key_valid],
    queryFn: async () => (await api.get<Dataset[]>("/knowledge/datasets")).data,
    enabled: Boolean(status.data?.key_valid),
    retry: 1,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{t("knowledge.title")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("knowledge.subtitle")}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <BookOpen className="size-4" /> RAGFlow
            </CardTitle>
            <CardDescription>{status.data?.url || "-"}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {status.isLoading ? (
              <Skeleton className="h-6 w-24" />
            ) : (
              <Badge variant={status.data?.healthy ? "success" : "warning"}>
                {status.data?.healthy ? t("knowledge.healthy") : t("knowledge.offline")}
              </Badge>
            )}
            <div className="text-xs text-muted-foreground">
              {status.data?.configured ? t("knowledge.configured") : t("knowledge.notConfigured")}
            </div>
            {status.data?.error ? (
              <p className="text-xs text-destructive">{status.data.error}</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("knowledge.datasetCount")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{status.data?.dataset_count ?? 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("knowledge.configure")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link to="/settings">{t("knowledge.configure")}</Link>
            </Button>
            {status.data?.web_url ? (
              <Button variant="outline" asChild>
                <a href={status.data.web_url} target="_blank" rel="noreferrer">
                  <ExternalLink className="size-4" /> {t("knowledge.openRagflow")}
                </a>
              </Button>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>{t("knowledge.datasets")}</CardTitle>
            <CardDescription>{t("knowledge.datasetsHint")}</CardDescription>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void status.refetch();
              void datasets.refetch();
            }}
          >
            <RefreshCw className="size-3.5" /> {t("common.refresh")}
          </Button>
        </CardHeader>
        <CardContent>
          {!status.data?.key_valid ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("knowledge.notConfiguredHint")}
            </p>
          ) : datasets.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : datasets.isError ? (
            <p className="py-8 text-center text-sm text-destructive">
              {datasets.error.message}
            </p>
          ) : (datasets.data ?? []).length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("knowledge.empty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{t("knowledge.name")}</th>
                    <th className="py-2 pr-4 font-medium">{t("knowledge.description")}</th>
                    <th className="py-2 pr-4 font-medium">{t("knowledge.documents")}</th>
                    <th className="py-2 pr-4 font-medium">{t("knowledge.chunks")}</th>
                    <th className="py-2 font-medium">{t("knowledge.id")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(datasets.data ?? []).map((dataset, index) => (
                    <tr key={text(dataset.id) || index} className="border-b last:border-0">
                      <td className="py-3 pr-4 font-medium">
                        {text(dataset.name) || `Dataset ${index + 1}`}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {text(dataset.description) || "-"}
                      </td>
                      <td className="py-3 pr-4">{text(dataset.document_count) || "0"}</td>
                      <td className="py-3 pr-4">{text(dataset.chunk_count) || "0"}</td>
                      <td className="py-3 font-mono text-xs text-muted-foreground">
                        {text(dataset.id) || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
