import { QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import { api } from "@/api/client";
import type { OnboardingStatus } from "@/api/types";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { queryClient } from "@/lib/queryClient";
import { AgentsPage } from "@/pages/AgentsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { KnowledgePage } from "@/pages/KnowledgePage";
import { McpServersPage } from "@/pages/McpServersPage";
import { OnboardingPage } from "@/pages/OnboardingPage";
import { ProjectDetailPage } from "@/pages/ProjectDetailPage";
import { ProjectsPage } from "@/pages/ProjectsPage";
import { RequirementDetailPage } from "@/pages/RequirementDetailPage";
import { RunsPage } from "@/pages/RunsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SkillsPage } from "@/pages/SkillsPage";
import { ThemeProvider } from "@/theme/ThemeProvider";

function Centered({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <div className="max-w-md space-y-3 text-center">{children}</div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/requirements/:requirementId" element={<RequirementDetailPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/mcp" element={<McpServersPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function Gate() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const onboarding = useQuery({
    queryKey: ["onboarding"],
    queryFn: async () => (await api.get<OnboardingStatus>("/onboarding/status")).data,
    retry: 1,
  });

  if (onboarding.isLoading) {
    return (
      <Centered>
        <p className="text-sm text-muted-foreground">{t("onboarding.loading")}</p>
      </Centered>
    );
  }

  if (onboarding.isError) {
    return (
      <Centered>
        <p className="text-sm font-medium">{t("errors.loadFailed")}</p>
        <p className="text-xs text-muted-foreground">{onboarding.error.message}</p>
        <Button onClick={() => onboarding.refetch()}>{t("onboarding.retry")}</Button>
      </Centered>
    );
  }

  if (onboarding.data && !onboarding.data.completed) {
    return (
      <OnboardingPage
        initialStatus={onboarding.data}
        onChanged={async () => {
          await onboarding.refetch();
          await queryClient.invalidateQueries();
        }}
      />
    );
  }

  return <AppRoutes />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <Gate />
          <Toaster richColors position="bottom-right" />
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
