import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Project } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/utils";

export function ProjectsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState("python-web");

  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: async () => (await api.get<Project[]>("/projects")).data,
  });

  const create = useMutation({
    mutationFn: async () =>
      (
        await api.post<Project>("/projects", {
          name,
          slug,
          description,
          template,
        })
      ).data,
    onSuccess: (project) => {
      toast.success(t("projects.create"));
      setOpen(false);
      setName("");
      setSlug("");
      setDescription("");
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{t("projects.title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("projects.subtitle")}</p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus className="size-4" /> {t("projects.newProject")}
        </Button>
      </div>

      {projects.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : (projects.data ?? []).length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <div className="text-lg font-medium">{t("projects.empty")}</div>
            <p className="max-w-md text-sm text-muted-foreground">{t("projects.emptyHint")}</p>
            <Button onClick={() => setOpen(true)}>
              <Plus className="size-4" /> {t("projects.create")}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(projects.data ?? []).map((project) => (
            <Card key={project.id} className="flex flex-col">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="truncate">{project.name}</CardTitle>
                    <CardDescription className="mt-1 truncate">{project.slug}</CardDescription>
                  </div>
                  <Button variant="ghost" size="icon" asChild>
                    <a href={project.repo_url} target="_blank" rel="noreferrer" title={t("projects.openRepo")}>
                      <ExternalLink className="size-4" />
                    </a>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col justify-between gap-4">
                <p className="line-clamp-3 text-sm text-muted-foreground">
                  {project.description || t("common.noData")}
                </p>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{t("projects.requirementCount", { count: project.requirement_count })}</span>
                  <span>{formatDate(project.created_at)}</span>
                </div>
                <Button variant="outline" asChild>
                  <Link to={`/projects/${project.id}`}>{t("requirements.viewDetails")}</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t("projects.newProject")}
        description={t("projects.subtitle")}
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={!name.trim() || create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? t("common.creating") : t("projects.create")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="project-name">{t("projects.name")}</Label>
            <Input
              id="project-name"
              value={name}
              placeholder={t("projects.namePlaceholder")}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-slug">{t("projects.slug")}</Label>
            <Input
              id="project-slug"
              value={slug}
              placeholder="my-content-site"
              onChange={(event) => setSlug(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t("projects.slugHint")}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-description">{t("projects.description")}</Label>
            <Textarea
              id="project-description"
              value={description}
              placeholder={t("projects.descriptionPlaceholder")}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-template">{t("projects.template")}</Label>
            <Select
              id="project-template"
              value={template}
              onChange={(event) => setTemplate(event.target.value)}
            >
              <option value="python-web">{t("projects.templatePythonWeb")}</option>
              <option value="blank">{t("projects.templateBlank")}</option>
            </Select>
            <p className="text-xs text-muted-foreground">
              {template === "python-web"
                ? t("projects.templatePythonWebHint")
                : t("projects.templateBlankHint")}
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
}
