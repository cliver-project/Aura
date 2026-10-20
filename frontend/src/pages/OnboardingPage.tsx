import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Circle, KeyRound, Terminal, User } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { OnboardingStatus } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { Select } from "@/components/ui/select";
import { LanguageSwitcher } from "@/i18n/LanguageSwitcher";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/theme/ThemeToggle";

interface OnboardingPageProps {
  initialStatus: OnboardingStatus;
  onChanged: () => Promise<unknown>;
}

function Step({
  index,
  title,
  description,
  done,
  children,
}: {
  index: number;
  title: string;
  description: string;
  done: boolean;
  children: React.ReactNode;
}) {
  return (
    <Card className={cn(done && "border-emerald-500/40")}>
      <CardHeader className="flex-row items-start gap-3">
        <span
          className={cn(
            "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
            done ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-muted",
          )}
        >
          {done ? <CheckCircle2 className="size-4" /> : index}
        </span>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pl-14">{children}</CardContent>
    </Card>
  );
}

export function OnboardingPage({ initialStatus, onChanged }: OnboardingPageProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState(initialStatus);
  const [username, setUsername] = useState(initialStatus.suggested.username);
  const [fullName, setFullName] = useState(initialStatus.suggested.full_name);
  const [email, setEmail] = useState(initialStatus.suggested.email);
  const [gitName, setGitName] = useState(
    initialStatus.git.user_name || initialStatus.suggested.full_name,
  );
  const [gitEmail, setGitEmail] = useState(
    initialStatus.git.user_email || initialStatus.suggested.email,
  );
  const [selectedKey, setSelectedKey] = useState(
    initialStatus.ssh.keys.find((key) => key.registered)?.path ??
      initialStatus.ssh.keys[0]?.path ??
      "",
  );
  const [applyGit, setApplyGit] = useState(true);
  const [ragflowUrl, setRagflowUrl] = useState(initialStatus.ragflow.url);
  const [ragflowApiKey, setRagflowApiKey] = useState("");
  const [ragflowAccountEmail, setRagflowAccountEmail] = useState(
    initialStatus.ragflow.account_email || initialStatus.suggested.email,
  );
  const [ragflowAccountPassword, setRagflowAccountPassword] = useState("");

  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    if (!selectedKey && status.ssh.keys.length > 0) {
      setSelectedKey(status.ssh.keys[0].path);
    }
  }, [selectedKey, status.ssh.keys]);

  const applyStatus = async (next: OnboardingStatus) => {
    setStatus(next);
    await onChanged();
  };

  const onError = (error: Error) => toast.error(error.message);

  const saveIdentity = useMutation({
    mutationFn: async () =>
      (
        await api.post<OnboardingStatus>("/onboarding/gitea-user", {
          username,
          full_name: fullName,
          email,
        })
      ).data,
    onSuccess: async (next) => {
      await applyStatus(next);
      toast.success(t("onboarding.identitySaved"));
    },
    onError,
  });

  const generateKey = useMutation({
    mutationFn: async () =>
      (await api.post<OnboardingStatus>("/onboarding/ssh-key/generate", { email })).data,
    onSuccess: async (next) => {
      await applyStatus(next);
      toast.success(t("onboarding.sshGenerated"));
    },
    onError,
  });

  const registerKey = useMutation({
    mutationFn: async () =>
      (
        await api.post<OnboardingStatus>("/onboarding/ssh-key/register", {
          path: selectedKey,
        })
      ).data,
    onSuccess: async (next) => {
      await applyStatus(next);
      toast.success(t("onboarding.sshRegistered"));
    },
    onError,
  });

  const saveGit = useMutation({
    mutationFn: async () =>
      (
        await api.post<OnboardingStatus>("/onboarding/git-identity", {
          user_name: gitName,
          user_email: gitEmail,
        })
      ).data,
    onSuccess: async (next) => {
      await applyStatus(next);
      toast.success(t("onboarding.gitSaved"));
    },
    onError,
  });

  const configureRagflow = useMutation({
    mutationFn: async () =>
      (
        await api.post<OnboardingStatus>("/onboarding/ragflow", {
          url: ragflowUrl,
          api_key: ragflowApiKey,
          auto_create: true,
          account_email: ragflowAccountEmail,
          account_password: ragflowAccountPassword,
        })
      ).data,
    onSuccess: async (next) => {
      await applyStatus(next);
      toast.success(t("onboarding.ragflowSaved"));
    },
    onError,
  });

  const complete = useMutation({
    mutationFn: async () => (await api.post<OnboardingStatus>("/onboarding/complete")).data,
    onSuccess: async (next) => {
      setStatus(next);
      await onChanged();
      toast.success(t("onboarding.completed"));
    },
    onError,
  });

  const identityDone = !status.missing.includes("gitea_identity");
  const sshDone = !status.missing.includes("ssh_key");
  const gitDone = !status.missing.includes("git_identity");
  const ragflowDone = !status.missing.includes("ragflow");
  const allDone = status.missing.length === 0;
  const selectedKeyInfo = status.ssh.keys.find((key) => key.path === selectedKey);

  return (
    <div className="min-h-svh bg-muted/30">
      <header className="mx-auto flex max-w-4xl items-center justify-between px-4 py-5 md:px-6">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            A
          </span>
          <span className="text-sm font-semibold">{t("app.title")}</span>
        </div>
        <div className="flex items-center gap-1">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 pb-16 md:px-6">
        <div className="mb-6 space-y-2 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">{t("onboarding.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("onboarding.subtitle")}</p>
          <p className="text-xs text-muted-foreground">
            {t("onboarding.osUser", { user: status.os_user })}
          </p>
        </div>

        <div className="space-y-4">
          <Step
            index={1}
            title={t("onboarding.stepIdentity")}
            description={t("onboarding.stepIdentityDesc")}
            done={identityDone}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="onboarding-username">{t("onboarding.username")}</Label>
                <Input
                  id="onboarding-username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="onboarding-fullname">{t("onboarding.fullName")}</Label>
                <Input
                  id="onboarding-fullname"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="onboarding-email">{t("onboarding.email")}</Label>
              <Input
                id="onboarding-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">{t("onboarding.usernameHint")}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={() => saveIdentity.mutate()}
                disabled={!username.trim() || !email.trim() || saveIdentity.isPending}
              >
                <User className="size-4" />
                {saveIdentity.isPending
                  ? t("onboarding.savingIdentity")
                  : t("onboarding.saveIdentity")}
              </Button>
              {status.gitea.exists ? (
                <Badge variant="success">
                  {t("onboarding.connected", { username: status.gitea.username })}
                </Badge>
              ) : (
                <Badge variant="muted">{t("onboarding.notCreated")}</Badge>
              )}
            </div>
            {status.gitea.error ? (
              <p className="text-xs text-destructive">{status.gitea.error}</p>
            ) : null}
            <p className="text-xs text-muted-foreground">{t("onboarding.passwordHint")}</p>
          </Step>

          <Step
            index={2}
            title={t("onboarding.stepSsh")}
            description={t("onboarding.stepSshDesc")}
            done={sshDone}
          >
            {status.ssh.keys.length === 0 ? (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">{t("onboarding.noSshKeys")}</p>
                <Button
                  variant="outline"
                  onClick={() => generateKey.mutate()}
                  disabled={generateKey.isPending}
                >
                  <KeyRound className="size-4" />
                  {generateKey.isPending
                    ? t("onboarding.generating")
                    : t("onboarding.generateSshKey")}
                </Button>
                <p className="text-xs text-muted-foreground">
                  {t("onboarding.sshGenerateHint")}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="onboarding-key">{t("onboarding.selectKey")}</Label>
                  <Select
                    id="onboarding-key"
                    value={selectedKey}
                    onChange={(event) => setSelectedKey(event.target.value)}
                  >
                    {status.ssh.keys.map((key) => (
                      <option key={key.path} value={key.path}>
                        {key.path} ({key.type})
                      </option>
                    ))}
                  </Select>
                </div>
                {selectedKeyInfo ? (
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <p className="font-mono">
                      {t("onboarding.fingerprint", {
                        fingerprint: selectedKeyInfo.fingerprint || "-",
                      })}
                    </p>
                    <Badge variant={selectedKeyInfo.registered ? "success" : "warning"}>
                      {selectedKeyInfo.registered
                        ? t("onboarding.sshRegistered")
                        : t("onboarding.sshNotRegistered")}
                    </Badge>
                  </div>
                ) : null}
                <Button
                  variant="outline"
                  onClick={() => registerKey.mutate()}
                  disabled={
                    !selectedKey ||
                    Boolean(selectedKeyInfo?.registered) ||
                    registerKey.isPending
                  }
                >
                  <Terminal className="size-4" />
                  {registerKey.isPending
                    ? t("onboarding.registering")
                    : t("onboarding.registerKey")}
                </Button>
              </div>
            )}
          </Step>

          <Step
            index={3}
            title={t("onboarding.stepGit")}
            description={t("onboarding.stepGitDesc")}
            done={gitDone}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="onboarding-git-name">{t("onboarding.gitName")}</Label>
                <Input
                  id="onboarding-git-name"
                  value={gitName}
                  onChange={(event) => setGitName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="onboarding-git-email">{t("onboarding.gitEmail")}</Label>
                <Input
                  id="onboarding-git-email"
                  type="email"
                  value={gitEmail}
                  onChange={(event) => setGitEmail(event.target.value)}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={applyGit}
                onChange={(event) => setApplyGit(event.target.checked)}
              />
              {t("onboarding.applyGit")}
            </label>
            <p className="text-xs text-muted-foreground">
              {status.git.matches_gitea
                ? t("onboarding.matchesGitea")
                : t("onboarding.gitMismatch")}
            </p>
            <Button
              variant="outline"
              onClick={() => saveGit.mutate()}
              disabled={!applyGit || !gitName.trim() || !gitEmail.trim() || saveGit.isPending}
            >
              {saveGit.isPending ? t("onboarding.applying") : t("onboarding.saveGit")}
            </Button>
          </Step>

          <Step
            index={4}
            title={t("onboarding.stepRagflow")}
            description={t("onboarding.stepRagflowDesc")}
            done={ragflowDone}
          >
            <div className="space-y-2">
              <Label htmlFor="onboarding-ragflow-url">{t("onboarding.ragflowUrl")}</Label>
              <Input
                id="onboarding-ragflow-url"
                value={ragflowUrl}
                onChange={(event) => setRagflowUrl(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">{t("onboarding.ragflowHint")}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="onboarding-ragflow-account-email">
                  {t("onboarding.ragflowAccountEmail")}
                </Label>
                <Input
                  id="onboarding-ragflow-account-email"
                  type="email"
                  value={ragflowAccountEmail}
                  onChange={(event) => setRagflowAccountEmail(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="onboarding-ragflow-account-password">
                  {t("onboarding.ragflowAccountPassword")}
                </Label>
                <PasswordInput
                  id="onboarding-ragflow-account-password"
                  value={ragflowAccountPassword}
                  placeholder={t("onboarding.ragflowAccountPasswordPlaceholder")}
                  onChange={(event) => setRagflowAccountPassword(event.target.value)}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{t("onboarding.ragflowAccountHint")}</p>
            <div className="space-y-2">
              <Label htmlFor="onboarding-ragflow-key">{t("onboarding.ragflowApiKey")}</Label>
              <PasswordInput
                id="onboarding-ragflow-key"
                value={ragflowApiKey}
                placeholder={t("onboarding.ragflowKeyOptional")}
                onChange={(event) => setRagflowApiKey(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">{t("onboarding.ragflowKeyHint")}</p>
              {status.ragflow.account_password_configured ? (
                <p className="text-xs text-muted-foreground">
                  {t("onboarding.ragflowPasswordConfigured")}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={() => configureRagflow.mutate()}
                disabled={!ragflowUrl.trim() || configureRagflow.isPending}
              >
                {configureRagflow.isPending
                  ? t("onboarding.configuringRagflow")
                  : t("onboarding.configureRagflow")}
              </Button>
              <Badge variant={status.ragflow.healthy ? "success" : "warning"}>
                {status.ragflow.healthy
                  ? t("onboarding.ragflowHealthy")
                  : t("onboarding.ragflowOffline")}
              </Badge>
              {status.ragflow.api_key_configured ? (
                <Badge variant="success">{t("onboarding.ragflowKeySaved")}</Badge>
              ) : null}
            </div>
            {status.ragflow.web_url ? (
              <a
                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                href={status.ragflow.web_url}
                target="_blank"
                rel="noreferrer"
              >
                {t("onboarding.openRagflow")}
              </a>
            ) : null}
            {status.ragflow.error ? (
              <p className="text-xs text-destructive">{status.ragflow.error}</p>
            ) : null}
          </Step>

          <Step
            index={5}
            title={t("onboarding.stepFinish")}
            description={t("onboarding.stepFinishDesc")}
            done={allDone && status.completed}
          >
            <div className="space-y-2 text-sm">
              {[
                ["gitea_identity", t("onboarding.missingGitea")],
                ["ssh_key", t("onboarding.missingSsh")],
                ["git_identity", t("onboarding.missingGit")],
                ["ragflow", t("onboarding.missingRagflow")],
              ].map(([key, label]) => (
                <div key={key} className="flex items-center gap-2">
                  {status.missing.includes(key) ? (
                    <Circle className="size-4 text-muted-foreground" />
                  ) : (
                    <CheckCircle2 className="size-4 text-emerald-500" />
                  )}
                  {label}
                </div>
              ))}
            </div>
            {!allDone ? (
              <p className="text-xs text-muted-foreground">
                {t("onboarding.missing")}: {status.missing.join(", ")}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">{t("onboarding.allDone")}</p>
            )}
            <Button
              onClick={() => complete.mutate()}
              disabled={!allDone || complete.isPending}
            >
              {complete.isPending ? t("onboarding.finishing") : t("onboarding.finish")}
            </Button>
          </Step>
        </div>
      </main>
    </div>
  );
}
