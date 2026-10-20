import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { McpServer } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

interface McpForm {
  name: string;
  description: string;
  transport: string;
  command: string;
  args: string;
  env: string;
  url: string;
  headers: string;
  enabled: boolean;
}

const EMPTY: McpForm = {
  name: "",
  description: "",
  transport: "stdio",
  command: "",
  args: "",
  env: "",
  url: "",
  headers: "",
  enabled: true,
};

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseKeyValues(value: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of parseLines(value)) {
    const index = line.indexOf("=");
    if (index <= 0) continue;
    result[line.slice(0, index).trim()] = line.slice(index + 1).trim();
  }
  return result;
}

function stringifyKeyValues(value?: Record<string, string>): string {
  return Object.entries(value ?? {})
    .map(([key, item]) => `${key}=${item}`)
    .join("\n");
}

export function McpServersPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<McpServer | null>(null);
  const [form, setForm] = useState<McpForm>(EMPTY);

  const servers = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: async () => (await api.get<McpServer[]>("/mcp-servers")).data,
  });

  const invalidate = () => void queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        description: form.description,
        transport: form.transport,
        command: form.command,
        args: parseLines(form.args),
        env: parseKeyValues(form.env),
        url: form.url,
        headers: parseKeyValues(form.headers),
        enabled: form.enabled,
      };
      if (editing) {
        return (await api.patch<McpServer>(`/mcp-servers/${editing.id}`, payload)).data;
      }
      return (await api.post<McpServer>("/mcp-servers", payload)).data;
    },
    onSuccess: () => {
      toast.success(editing ? t("mcp.editTitle") : t("mcp.createTitle"));
      setOpen(false);
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: async (server: McpServer) => api.delete(`/mcp-servers/${server.id}`),
    onSuccess: () => {
      toast.success(t("common.delete"));
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setOpen(true);
  };

  const openEdit = (server: McpServer) => {
    setEditing(server);
    setForm({
      name: server.name,
      description: server.description,
      transport: server.transport,
      command: server.command,
      args: server.args.join("\n"),
      env: stringifyKeyValues(server.env),
      url: server.url,
      headers: stringifyKeyValues(server.headers),
      enabled: server.enabled,
    });
    setOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{t("mcp.title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("mcp.subtitle")}</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" /> {t("mcp.newServer")}
        </Button>
      </div>

      {servers.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <Skeleton key={index} className="h-36 w-full" />
          ))}
        </div>
      ) : (servers.data ?? []).length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
            <p className="text-sm text-muted-foreground">{t("mcp.empty")}</p>
            <p className="text-xs text-muted-foreground">{t("mcp.createHint")}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(servers.data ?? []).map((server) => (
            <Card key={server.id} className={!server.enabled ? "opacity-60" : undefined}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <CardTitle className="truncate">{server.name}</CardTitle>
                    <CardDescription className="mt-1">{server.description || "-"}</CardDescription>
                  </div>
                  <Badge variant={server.transport === "stdio" ? "secondary" : "info"}>
                    {server.transport}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="truncate font-mono text-xs text-muted-foreground">
                  {server.transport === "stdio" ? server.command : server.url}
                </p>
                <div className="flex flex-wrap gap-1">
                  {!server.enabled ? <Badge variant="warning">{t("common.disabled")}</Badge> : null}
                  <Badge variant="muted">{Object.keys(server.env).length} env</Badge>
                  <Badge variant="muted">{Object.keys(server.headers).length} headers</Badge>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEdit(server)}>
                    <Pencil className="size-3.5" /> {t("common.edit")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => {
                      if (window.confirm(t("mcp.deleteConfirm"))) remove.mutate(server);
                    }}
                  >
                    <Trash2 className="size-3.5" /> {t("common.delete")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? t("mcp.editTitle") : t("mcp.createTitle")}
        className="max-w-3xl"
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button disabled={!form.name.trim() || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? t("common.saving") : t("common.save")}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="mcp-name">{t("mcp.name")}</Label>
              <Input
                id="mcp-name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp-transport">{t("mcp.transport")}</Label>
              <Select
                id="mcp-transport"
                value={form.transport}
                onChange={(event) => setForm({ ...form, transport: event.target.value })}
              >
                <option value="stdio">{t("mcp.stdio")}</option>
                <option value="http">{t("mcp.http")}</option>
                <option value="sse">{t("mcp.sse")}</option>
              </Select>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="mcp-description">{t("mcp.description")}</Label>
            <Input
              id="mcp-description"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </div>

          {form.transport === "stdio" ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="mcp-command">{t("mcp.command")}</Label>
                <Input
                  id="mcp-command"
                  value={form.command}
                  placeholder="npx"
                  onChange={(event) => setForm({ ...form, command: event.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mcp-args">{t("mcp.args")}</Label>
                <Textarea
                  id="mcp-args"
                  value={form.args}
                  placeholder={"-y\n@modelcontextprotocol/server-filesystem"}
                  onChange={(event) => setForm({ ...form, args: event.target.value })}
                />
                <p className="text-xs text-muted-foreground">{t("mcp.argsHint")}</p>
              </div>
            </>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="mcp-url">{t("mcp.url")}</Label>
              <Input
                id="mcp-url"
                value={form.url}
                placeholder="http://localhost:9000/mcp"
                onChange={(event) => setForm({ ...form, url: event.target.value })}
              />
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="mcp-env">{t("mcp.env")}</Label>
              <Textarea
                id="mcp-env"
                value={form.env}
                placeholder="API_KEY=secret"
                onChange={(event) => setForm({ ...form, env: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">{t("mcp.envHint")}</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mcp-headers">{t("mcp.headers")}</Label>
              <Textarea
                id="mcp-headers"
                value={form.headers}
                placeholder="Authorization=Bearer token"
                onChange={(event) => setForm({ ...form, headers: event.target.value })}
              />
              <p className="text-xs text-muted-foreground">{t("mcp.headersHint")}</p>
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
