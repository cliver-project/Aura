import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { SettingsResponse } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const EDITABLE = [
  "claude_bin",
  "default_model",
  "anthropic_base_url",
  "anthropic_auth_token",
  "anthropic_model",
  "anthropic_default_opus_model",
  "anthropic_default_sonnet_model",
  "anthropic_default_haiku_model",
  "claude_code_subagent_model",
  "claude_code_effort_level",
  "claude_code_auto_compact_window",
  "claude_code_disable_unknown_model_window_enforcement",
  "model_prices",
  "permission_mode",
  "max_budget_usd",
  "max_concurrent_runs",
  "agent_timeout_seconds",
  "gitea_url",
  "gitea_user",
  "gitea_owner",
  "gitea_token",
  "gitea_language",
  "workspace_dir",
  "public_url",
  "database_admin_url",
  "ragflow_url",
  "ragflow_api_key",
  "ragflow_account_email",
  "ragflow_account_password",
  "ragflow_mcp_url",
  "ragflow_language",
  "default_locale",
  "default_theme",
  "auto_pipeline",
] as const;

type Values = Record<string, unknown>;
type ModelPrice = {
  input: number;
  output: number;
  cache_read: number;
  cache_write: number;
};
type ModelPrices = Record<string, Partial<ModelPrice>>;

export function SettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [values, setValues] = useState<Values>({});
  const [newModel, setNewModel] = useState("");

  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: async () => (await api.get<SettingsResponse>("/settings")).data,
  });

  useEffect(() => {
    if (settings.data) setValues(settings.data.values);
  }, [settings.data]);

  const save = useMutation({
    mutationFn: async () => {
      const payload: Values = {};
      for (const key of EDITABLE) payload[key] = values[key];
      return (await api.patch<SettingsResponse>("/settings", { values: payload })).data;
    },
    onSuccess: async (data) => {
      const refreshed = await api.get<SettingsResponse>("/settings");
      setValues(refreshed.data.values);
      if (data.warnings?.length) {
        for (const warning of data.warnings) toast.warning(warning);
      } else {
        toast.success(t("settings.saved"));
      }
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (error: Error) => toast.error(`${t("settings.saveFailed")}: ${error.message}`),
  });

  const resetOnboarding = useMutation({
    mutationFn: async () => api.post("/onboarding/reset"),
    onSuccess: () => {
      window.location.assign("/");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const set = (key: string, value: unknown) =>
    setValues((current) => ({ ...current, [key]: value }));
  const source = (key: string) => settings.data?.sources[key] ?? "default";
  const locked = (key: string) => source(key) === "environment";

  const modelPrices = (values.model_prices ?? {}) as ModelPrices;
  const pricesLocked = locked("model_prices") || save.isPending;
  const updateModelPrice = (model: string, field: keyof ModelPrice, raw: string) => {
    const parsed = Number(raw);
    set("model_prices", {
      ...modelPrices,
      [model]: {
        ...modelPrices[model],
        [field]: Number.isFinite(parsed) ? parsed : 0,
      },
    });
  };
  const removeModel = (model: string) => {
    const next = { ...modelPrices };
    delete next[model];
    set("model_prices", next);
  };
  const addModel = () => {
    const name = newModel.trim();
    if (!name) return;
    set("model_prices", {
      ...modelPrices,
      [name]: { input: 0, output: 0, cache_read: 0, cache_write: 0 },
    });
    setNewModel("");
  };

  const sourceBadge = (key: string) => {
    const value = source(key);
    return (
      <Badge variant={value === "environment" ? "warning" : value === "database" ? "info" : "muted"}>
        {t(
          value === "environment"
            ? "settings.environment"
            : value === "initial"
              ? "settings.initial"
              : value === "database"
                ? "settings.database"
                : "settings.default",
        )}
      </Badge>
    );
  };

  const field = (
    key: string,
    labelKey: string,
    options?: {
      hintKey?: string;
      type?: string;
      secret?: boolean;
      select?: { value: string; label: string }[];
    },
  ) => {
    const disabled = locked(key) || save.isPending;
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={`setting-${key}`}>{t(labelKey)}</Label>
          {sourceBadge(key)}
        </div>
        {options?.select ? (
          <Select
            id={`setting-${key}`}
            value={String(values[key] ?? "")}
            disabled={disabled}
            onChange={(event) => set(key, event.target.value)}
          >
            {options.select.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        ) : options?.secret ? (
          <PasswordInput
            id={`setting-${key}`}
            value={String(values[key] ?? "")}
            disabled={disabled}
            onChange={(event) => set(key, event.target.value)}
          />
        ) : (
          <Input
            id={`setting-${key}`}
            type={options?.type ?? "text"}
            value={String(values[key] ?? "")}
            disabled={disabled}
            onChange={(event) => set(key, event.target.value)}
          />
        )}
        {options?.hintKey ? (
          <p className="text-xs text-muted-foreground">{t(options.hintKey)}</p>
        ) : null}
      </div>
    );
  };

  if (settings.isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{t("settings.title")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("settings.subtitle")}</p>
        </div>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? t("common.saving") : t("common.save")}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupProvider")}</CardTitle>
          <CardDescription>{t("settings.providerHint")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("anthropic_base_url", "settings.anthropicBaseUrl")}
          {field("anthropic_auth_token", "settings.anthropicAuthToken", {
            secret: true,
            hintKey: "settings.secretHint",
          })}
          {field("anthropic_model", "settings.anthropicModel")}
          {field("anthropic_default_opus_model", "settings.anthropicOpusModel")}
          {field("anthropic_default_sonnet_model", "settings.anthropicSonnetModel")}
          {field("anthropic_default_haiku_model", "settings.anthropicHaikuModel")}
          {field("claude_code_subagent_model", "settings.subagentModel")}
          {field("claude_code_effort_level", "settings.effortLevel")}
          {field("claude_code_auto_compact_window", "settings.autoCompactWindow")}
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input
              type="checkbox"
              checked={Boolean(values.claude_code_disable_unknown_model_window_enforcement)}
              disabled={
                locked("claude_code_disable_unknown_model_window_enforcement") || save.isPending
              }
              onChange={(event) =>
                set("claude_code_disable_unknown_model_window_enforcement", event.target.checked)
              }
            />
            {t("settings.disableWindowEnforcement")}
            {sourceBadge("claude_code_disable_unknown_model_window_enforcement")}
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle>{t("settings.groupPricing")}</CardTitle>
            {sourceBadge("model_prices")}
          </div>
          <CardDescription>{t("settings.modelPricesHint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {Object.keys(modelPrices).length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("settings.modelPricesEmpty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="py-2 pr-3 font-medium">{t("settings.modelName")}</th>
                    <th className="py-2 pr-3 font-medium">{t("settings.inputPrice")}</th>
                    <th className="py-2 pr-3 font-medium">{t("settings.outputPrice")}</th>
                    <th className="py-2 pr-3 font-medium">{t("settings.cacheReadPrice")}</th>
                    <th className="py-2 pr-3 font-medium">{t("settings.cacheWritePrice")}</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(modelPrices).map(([model, prices]) => (
                    <tr key={model} className="border-b last:border-0">
                      <td className="py-2 pr-3 font-mono text-xs">{model}</td>
                      {(["input", "output", "cache_read", "cache_write"] as const).map((field) => (
                        <td key={field} className="py-2 pr-3">
                          <Input
                            type="number"
                            min="0"
                            step="0.0001"
                            className="w-24"
                            value={String(prices[field] ?? 0)}
                            disabled={pricesLocked}
                            onChange={(event) => updateModelPrice(model, field, event.target.value)}
                          />
                        </td>
                      ))}
                      <td className="py-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={pricesLocked}
                          onClick={() => removeModel(model)}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={newModel}
              placeholder={t("settings.modelNamePlaceholder")}
              disabled={pricesLocked}
              onChange={(event) => setNewModel(event.target.value)}
            />
            <Button
              variant="outline"
              size="sm"
              disabled={pricesLocked || !newModel.trim()}
              onClick={addModel}
            >
              <Plus className="size-4" /> {t("settings.addModel")}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">{t("settings.modelPricesUnit")}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupAgent")}</CardTitle>
          <CardDescription>{t("agents.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("claude_bin", "settings.claudeBin", { hintKey: "settings.claudeBinHint" })}
          {field("default_model", "settings.defaultModel", { hintKey: "settings.defaultModelHint" })}
          {field("permission_mode", "settings.permissionMode", {
            select: [
              { value: "bypassPermissions", label: "bypassPermissions" },
              { value: "acceptEdits", label: "acceptEdits" },
              { value: "dontAsk", label: "dontAsk" },
              { value: "auto", label: "auto" },
              { value: "plan", label: "plan" },
            ],
          })}
          {field("max_budget_usd", "settings.maxBudget", { type: "number" })}
          {field("max_concurrent_runs", "settings.maxConcurrent", { type: "number" })}
          {field("agent_timeout_seconds", "settings.agentTimeout", { type: "number" })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupGitea")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("gitea_url", "settings.giteaUrl")}
          {field("gitea_user", "settings.giteaUser")}
          {field("gitea_owner", "settings.giteaOwner")}
          {field("gitea_token", "settings.giteaToken", {
            secret: true,
            hintKey: "settings.giteaTokenHint",
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupLanguages")}</CardTitle>
          <CardDescription>{t("settings.languageHint")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("gitea_language", "settings.giteaLanguage", {
            select: [
              { value: "en-US", label: "English" },
              { value: "zh-CN", label: "简体中文" },
              { value: "zh-TW", label: "繁體中文" },
            ],
          })}
          {field("ragflow_language", "settings.ragflowLanguage", {
            select: [
              { value: "en", label: "English" },
              { value: "zh-Hans", label: "简体中文" },
              { value: "zh-Hant", label: "繁體中文" },
            ],
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupRuntime")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("workspace_dir", "settings.workspaceDir")}
          {field("public_url", "settings.publicUrl")}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupDatabase")}</CardTitle>
          <CardDescription>{t("settings.databaseAdminHint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {field("database_admin_url", "settings.databaseAdminUrl")}
          <Button variant="outline" asChild>
            <a
              href={String(values.database_admin_url ?? "http://127.0.0.1:8081")}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink className="size-4" /> {t("settings.openDatabase")}
            </a>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupKnowledge")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("ragflow_url", "settings.ragflowUrl")}
          {field("ragflow_api_key", "settings.ragflowApiKey", {
            secret: true,
            hintKey: "settings.secretHint",
          })}
          {field("ragflow_account_email", "settings.ragflowAccountEmail", {
            hintKey: "settings.ragflowAccountHint",
          })}
          {field("ragflow_account_password", "settings.ragflowAccountPassword", {
            secret: true,
            hintKey: "settings.ragflowAccountPasswordHint",
          })}
          {field("ragflow_mcp_url", "settings.ragflowMcpUrl", {
            hintKey: "settings.ragflowMcpUrlHint",
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.groupUi")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {field("default_locale", "settings.defaultLocale", {
            select: [
              { value: "en", label: "English" },
              { value: "zh", label: "中文" },
            ],
          })}
          {field("default_theme", "settings.defaultTheme", {
            select: [
              { value: "system", label: t("theme.system") },
              { value: "light", label: t("theme.light") },
              { value: "dark", label: t("theme.dark") },
            ],
          })}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(values.auto_pipeline)}
              disabled={locked("auto_pipeline") || save.isPending}
              onChange={(event) => set("auto_pipeline", event.target.checked)}
            />
            {t("settings.autoPipeline")}
            {sourceBadge("auto_pipeline")}
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.onboarding")}</CardTitle>
          <CardDescription>{t("settings.onboardingHint")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            onClick={() => resetOnboarding.mutate()}
            disabled={resetOnboarding.isPending}
          >
            {t("settings.runOnboarding")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
