import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Agent, McpServer, Skill } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface AgentForm {
  name: string;
  role_key: string;
  description: string;
  system_prompt: string;
  model: string;
  allowed_tools: string;
  env: string;
  skill_names: string[];
  mcp_server_ids: string[];
  enabled: boolean;
}

const EMPTY_FORM: AgentForm = {
  name: "",
  role_key: "",
  description: "",
  system_prompt: "",
  model: "",
  allowed_tools: "",
  env: "",
  skill_names: [],
  mcp_server_ids: [],
  enabled: true,
};

const parseEnv = (text: string): Record<string, string> =>
  Object.fromEntries(
    text
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#") && line.includes("="))
      .map((line) => {
        const index = line.indexOf("=");
        return [line.slice(0, index).trim(), line.slice(index + 1)];
      }),
  );

const formatEnv = (env: Record<string, string>): string =>
  Object.entries(env)
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");

export function AgentsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Agent | null>(null);
  const [form, setForm] = useState<AgentForm>(EMPTY_FORM);

  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: async () => (await api.get<Agent[]>("/agents")).data,
  });
  const skills = useQuery({
    queryKey: ["skills"],
    queryFn: async () => (await api.get<Skill[]>("/skills")).data,
  });
  const mcpServers = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: async () => (await api.get<McpServer[]>("/mcp-servers")).data,
  });

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["agents"] });

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        description: form.description,
        system_prompt: form.system_prompt,
        model: form.model,
        allowed_tools: form.allowed_tools
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        env: parseEnv(form.env),
        skill_names: form.skill_names,
        mcp_server_ids: form.mcp_server_ids,
        enabled: form.enabled,
      };
      if (editing) {
        return (await api.patch<Agent>(`/agents/${editing.id}`, payload)).data;
      }
      return (
        await api.post<Agent>("/agents", {
          ...payload,
          role_key: form.role_key,
        })
      ).data;
    },
    onSuccess: () => {
      toast.success(editing ? t("agents.editTitle") : t("agents.createTitle"));
      setOpen(false);
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: async (agent: Agent) => api.delete(`/agents/${agent.id}`),
    onSuccess: () => {
      toast.success(t("common.delete"));
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setOpen(true);
  };

  const openEdit = (agent: Agent) => {
    setEditing(agent);
    setForm({
      name: agent.name,
      role_key: agent.role_key,
      description: agent.description,
      system_prompt: agent.system_prompt,
      model: agent.model,
      allowed_tools: agent.allowed_tools.join(", "),
      env: formatEnv(agent.env ?? {}),
      skill_names: [...agent.skill_names],
      mcp_server_ids: [...agent.mcp_server_ids],
      enabled: agent.enabled,
    });
    setOpen(true);
  };

  const toggle = (field: "skill_names" | "mcp_server_ids", value: string) => {
    setForm((current) => {
      const existing = current[field];
      return {
        ...current,
        [field]: existing.includes(value)
          ? existing.filter((item) => item !== value)
          : [...existing, value],
      };
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{t("agents.title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("agents.subtitle")}</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" /> {t("agents.newAgent")}
        </Button>
      </div>

      {agents.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : (agents.data ?? []).length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("agents.empty")}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(agents.data ?? []).map((agent) => (
            <Card key={agent.id} className={cn(!agent.enabled && "opacity-60")}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="truncate">{agent.name}</CardTitle>
                    <CardDescription className="mt-1 font-mono text-xs">
                      {agent.role_key}
                    </CardDescription>
                  </div>
                  <Badge variant={agent.is_builtin ? "secondary" : "info"}>
                    {agent.is_builtin ? t("agents.builtin") : t("agents.custom")}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="line-clamp-3 text-sm text-muted-foreground">
                  {agent.description || t("common.noData")}
                </p>
                <div className="flex flex-wrap gap-1 text-xs">
                  <Badge variant="muted">
                    {t("agents.skillCount", { count: agent.skill_names.length })}
                  </Badge>
                  <Badge variant="muted">
                    {t("agents.mcpCount", { count: agent.mcp_server_ids.length })}
                  </Badge>
                  {Object.keys(agent.env ?? {}).length > 0 ? (
                    <Badge variant="muted">
                      {t("agents.envCount", { count: Object.keys(agent.env).length })}
                    </Badge>
                  ) : null}
                  {agent.model ? <Badge variant="outline">{agent.model}</Badge> : null}
                  {!agent.enabled ? <Badge variant="warning">{t("common.disabled")}</Badge> : null}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEdit(agent)}>
                    <Pencil className="size-3.5" /> {t("common.edit")}
                  </Button>
                  {!agent.is_builtin ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => {
                        if (window.confirm(t("agents.deleteConfirm"))) remove.mutate(agent);
                      }}
                    >
                      <Trash2 className="size-3.5" /> {t("common.delete")}
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t("agents.editTitle") : t("agents.createTitle")}
        className="max-w-3xl"
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={!form.name.trim() || (!editing && !form.role_key.trim()) || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="agent-name">{t("common.name")}</Label>
              <Input
                id="agent-name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-role">{t("agents.roleKey")}</Label>
              <Input
                id="agent-role"
                value={form.role_key}
                disabled={Boolean(editing)}
                onChange={(event) => setForm({ ...form, role_key: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">{t("agents.roleKeyHint")}</p>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-description">{t("common.description")}</Label>
            <Input
              id="agent-description"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-prompt">{t("agents.systemPrompt")}</Label>
            <Textarea
              id="agent-prompt"
              className="min-h-48 font-mono text-xs"
              value={form.system_prompt}
              onChange={(event) => setForm({ ...form, system_prompt: event.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="agent-env">{t("agents.envOverrides")}</Label>
            <Textarea
              id="agent-env"
              className="min-h-28 font-mono text-xs"
              placeholder="ANTHROPIC_BASE_URL=https://api.example.com/anthropic"
              value={form.env}
              onChange={(event) => setForm({ ...form, env: event.target.value })}
            />
            <p className="text-xs text-muted-foreground">{t("agents.envOverridesHint")}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="agent-model">{t("agents.model")}</Label>
              <Input
                id="agent-model"
                value={form.model}
                onChange={(event) => setForm({ ...form, model: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">{t("agents.modelHint")}</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent-tools">{t("agents.allowedTools")}</Label>
              <Input
                id="agent-tools"
                value={form.allowed_tools}
                placeholder="Bash, Edit, Read"
                onChange={(event) => setForm({ ...form, allowed_tools: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">{t("agents.allowedToolsHint")}</p>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>{t("agents.skills")}</Label>
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
                {(skills.data ?? []).map((skill) => (
                  <label key={skill.name} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.skill_names.includes(skill.name)}
                      onChange={() => toggle("skill_names", skill.name)}
                    />
                    <span className="font-mono text-xs">{skill.name}</span>
                  </label>
                ))}
                {(skills.data ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">{t("skills.empty")}</p>
                ) : null}
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t("agents.mcpServers")}</Label>
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
                {(mcpServers.data ?? []).map((server) => (
                  <label key={server.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.mcp_server_ids.includes(server.id)}
                      onChange={() => toggle("mcp_server_ids", server.id)}
                    />
                    <span className="text-xs">{server.name}</span>
                  </label>
                ))}
                {(mcpServers.data ?? []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">{t("mcp.empty")}</p>
                ) : null}
              </div>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
            />
            {t("common.enabled")}
          </label>
        </div>
      </Modal>
    </div>
  );
}
