import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Skill } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

const TEMPLATE = `---
name: my-skill
description: Describe when this skill should be used.
---

# My Skill

## When to use

Describe the trigger for this skill.

## Instructions

Write concrete, repeatable steps.

## Output contract

Describe the expected deliverable and its path.
`;

export function SkillsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [content, setContent] = useState(TEMPLATE);

  const skills = useQuery({
    queryKey: ["skills"],
    queryFn: async () => (await api.get<Skill[]>("/skills")).data,
  });

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["skills"] });

  const save = useMutation({
    mutationFn: async () => {
      if (editingName) {
        return (await api.put<Skill>(`/skills/${editingName}`, { content })).data;
      }
      return (await api.post<Skill>("/skills", { name, content })).data;
    },
    onSuccess: () => {
      toast.success(editingName ? t("skills.editTitle") : t("skills.createTitle"));
      setOpen(false);
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const refresh = useMutation({
    mutationFn: async () => (await api.post<Skill[]>("/skills/refresh")).data,
    onSuccess: () => {
      toast.success(t("skills.refresh"));
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const openCreate = () => {
    setEditingName(null);
    setName("");
    setContent(TEMPLATE);
    setOpen(true);
  };

  const openEdit = async (skill: Skill) => {
    try {
      const response = await api.get<{ content: string }>(`/skills/${skill.name}`);
      setEditingName(skill.name);
      setName(skill.name);
      setContent(response.data.content);
      setOpen(true);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{t("skills.title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("skills.subtitle")}</p>
          <p className="mt-1 text-xs text-muted-foreground">{t("skills.externalHint")}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            <RefreshCw className="size-4" /> {t("skills.refresh")}
          </Button>
          <Button onClick={openCreate}>
            <Plus className="size-4" /> {t("skills.createTitle")}
          </Button>
        </div>
      </div>

      {skills.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-36 w-full" />
          ))}
        </div>
      ) : (skills.data ?? []).length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            {t("skills.empty")}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(skills.data ?? []).map((skill) => (
            <Card key={skill.name}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="font-mono text-sm">{skill.name}</CardTitle>
                  <div className="flex flex-wrap items-center gap-1">
                    <Badge variant={skill.source === "builtin" ? "secondary" : "info"}>
                      {skill.source === "builtin"
                        ? t("skills.builtin")
                        : skill.source === "user"
                          ? t("skills.user")
                          : t("skills.project")}
                    </Badge>
                    {skill.read_only ? (
                      <Badge variant="muted">{t("skills.readOnly")}</Badge>
                    ) : null}
                  </div>
                </div>
                <CardDescription>{skill.description || t("common.noData")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="truncate font-mono text-xs text-muted-foreground">{skill.path}</p>
                {skill.read_only ? (
                  <p className="text-xs text-muted-foreground">{t("skills.readOnlyHint")}</p>
                ) : (
                  <Button variant="outline" size="sm" onClick={() => void openEdit(skill)}>
                    <Pencil className="size-3.5" /> {t("common.edit")}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editingName ? t("skills.editTitle") : t("skills.createTitle")}
        description={t("skills.contentHint")}
        className="max-w-4xl"
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={(!editingName && !name.trim()) || !content.trim() || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t("common.saving") : t("skills.save")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {!editingName ? (
            <div className="space-y-2">
              <Label htmlFor="skill-name">{t("skills.name")}</Label>
              <Input
                id="skill-name"
                value={name}
                placeholder="api-design"
                onChange={(event) => setName(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">{t("skills.nameHint")}</p>
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="skill-content">{t("skills.content")}</Label>
            <Textarea
              id="skill-content"
              className="min-h-[420px] font-mono text-xs"
              value={content}
              onChange={(event) => setContent(event.target.value)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
