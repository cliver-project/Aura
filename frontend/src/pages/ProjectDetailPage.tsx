import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, ExternalLink, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { KnowledgeDataset, Project, Requirement } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";

export function ProjectDetailPage() {
  const { t } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () => (await api.get<Project>(`/projects/${projectId}`)).data,
    enabled: Boolean(projectId),
  });

  const requirements = useQuery({
    queryKey: ["requirements", projectId],
    queryFn: async () =>
      (await api.get<Requirement[]>(`/projects/${projectId}/requirements`)).data,
    enabled: Boolean(projectId),
  });

  const datasets = useQuery({
    queryKey: ["knowledge-datasets"],
    queryFn: async () => (await api.get<KnowledgeDataset[]>("/knowledge/datasets")).data,
    enabled: Boolean(projectId),
    retry: false,
  });

  useEffect(() => {
    if (project.data) setSelectedDatasets(project.data.ragflow_dataset_ids ?? []);
  }, [project.data]);

  const saveKnowledge = useMutation({
    mutationFn: async () =>
      (
        await api.patch<Project>(`/projects/${projectId}`, {
          ragflow_dataset_ids: selectedDatasets,
        })
      ).data,
    onSuccess: () => {
      toast.success(t("projects.knowledgeSaved"));
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const toggleDataset = (id: string) => {
    setSelectedDatasets((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const create = useMutation({
    mutationFn: async () =>
      (
        await api.post<Requirement>(`/projects/${projectId}/requirements`, {
          title,
          idea,
        })
      ).data,
    onSuccess: (requirement) => {
      toast.success(t("requirements.create"));
      setOpen(false);
      setTitle("");
      setIdea("");
      void queryClient.invalidateQueries({ queryKey: ["requirements", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      navigate(`/requirements/${requirement.id}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  if (project.isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!project.data) {
    return <p className="text-sm text-muted-foreground">{t("errors.notFound")}</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/projects" className="flex items-center gap-1">
            <ArrowLeft className="size-4" /> {t("common.back")}
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{project.data.name}</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {project.data.description || t("common.noData")}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span className="font-mono">{project.data.slug}</span>
            <span>
              {t("common.createdAt")}: {formatDate(project.data.created_at)}
            </span>
            <span>{t("projects.requirementCount", { count: project.data.requirement_count })}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <a href={project.data.repo_url} target="_blank" rel="noreferrer">
              <ExternalLink className="size-4" /> {t("projects.openRepo")}
            </a>
          </Button>
          <Button onClick={() => setOpen(true)}>
            <Plus className="size-4" /> {t("requirements.newRequirement")}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="size-4" /> {t("projects.knowledgeBase")}
          </CardTitle>
          <CardDescription>{t("projects.knowledgeHint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {datasets.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : datasets.isError ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">{t("projects.knowledgeUnavailable")}</p>
              <Button variant="outline" size="sm" asChild>
                <Link to="/settings">{t("projects.knowledgeConfigure")}</Link>
              </Button>
            </div>
          ) : (datasets.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("projects.knowledgeEmpty")}</p>
          ) : (
            <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border p-3">
              {(datasets.data ?? []).map((dataset) => (
                <label key={dataset.id} className="flex items-start gap-2 py-1 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={selectedDatasets.includes(dataset.id)}
                    onChange={() => toggleDataset(dataset.id)}
                  />
                  <span className="min-w-0">
                    <span className="block font-medium">{dataset.name || dataset.id}</span>
                    <span className="block text-xs text-muted-foreground">
                      {dataset.description || dataset.id}
                    </span>
                  </span>
                  {typeof dataset.document_count === "number" ? (
                    <Badge variant="muted" className="ml-auto shrink-0">
                      {dataset.document_count}
                    </Badge>
                  ) : null}
                </label>
              ))}
            </div>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              {selectedDatasets.length === 0
                ? t("projects.knowledgeAll")
                : t("projects.knowledgeSelected", { count: selectedDatasets.length })}
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={saveKnowledge.isPending}
              onClick={() => saveKnowledge.mutate()}
            >
              {saveKnowledge.isPending ? t("common.saving") : t("projects.knowledgeSave")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("projects.requirements")}</CardTitle>
          <CardDescription>{t("requirements.emptyHint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {requirements.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (requirements.data ?? []).length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <p className="text-sm text-muted-foreground">{t("projects.noRequirements")}</p>
              <Button onClick={() => setOpen(true)}>
                <Plus className="size-4" /> {t("requirements.newRequirement")}
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{t("requirements.key")}</th>
                    <th className="py-2 pr-4 font-medium">{t("requirements.title")}</th>
                    <th className="py-2 pr-4 font-medium">{t("requirements.status")}</th>
                    <th className="py-2 pr-4 font-medium">{t("requirements.version")}</th>
                    <th className="py-2 pr-4 font-medium">{t("requirements.pr")}</th>
                    <th className="py-2 pr-4 font-medium">{t("requirements.ci")}</th>
                    <th className="py-2 font-medium">{t("requirements.created")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(requirements.data ?? []).map((requirement) => (
                    <tr key={requirement.id} className="border-b last:border-0">
                      <td className="py-3 pr-4 font-mono text-xs">{requirement.key}</td>
                      <td className="py-3 pr-4">
                        <Link className="font-medium hover:underline" to={`/requirements/${requirement.id}`}>
                          {requirement.title}
                        </Link>
                      </td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={requirement.status} />
                      </td>
                      <td className="py-3 pr-4">v{requirement.current_version}</td>
                      <td className="py-3 pr-4">
                        {requirement.pr_url ? (
                          <a
                            className="inline-flex items-center gap-1 text-blue-600 hover:underline dark:text-blue-400"
                            href={requirement.pr_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            #{requirement.pr_number} <ExternalLink className="size-3" />
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        {requirement.ci_status ? <StatusBadge status={requirement.ci_status} /> : "-"}
                      </td>
                      <td className="py-3 text-xs text-muted-foreground">
                        {formatDate(requirement.created_at)}
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
        open={open}
        onClose={() => setOpen(false)}
        title={t("requirements.newRequirement")}
        description={t("requirements.ideaPlaceholder")}
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={!title.trim() || !idea.trim() || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? t("common.creating") : t("requirements.create")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="requirement-title">{t("requirements.title")}</Label>
            <Input
              id="requirement-title"
              value={title}
              placeholder={t("requirements.titlePlaceholder")}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="requirement-idea">{t("requirements.idea")}</Label>
            <Textarea
              id="requirement-idea"
              className="min-h-40"
              value={idea}
              placeholder={t("requirements.ideaPlaceholder")}
              onChange={(event) => setIdea(event.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
