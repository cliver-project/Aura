import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Bot,
  Database,
  FolderGit2,
  LayoutDashboard,
  Plug,
  PlaySquare,
  Settings,
  Sparkles,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "@/api/client";
import type { Health, SettingsResponse } from "@/api/types";
import { LanguageSwitcher } from "@/i18n/LanguageSwitcher";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/theme/ThemeToggle";

const NAV = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", labelKey: "nav.projects", icon: FolderGit2 },
  { to: "/knowledge", labelKey: "nav.knowledge", icon: BookOpen },
  { to: "/agents", labelKey: "nav.agents", icon: Bot },
  { to: "/skills", labelKey: "nav.skills", icon: Sparkles },
  { to: "/mcp", labelKey: "nav.mcp", icon: Plug },
  { to: "/runs", labelKey: "nav.runs", icon: PlaySquare },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

export function AppLayout() {
  const { t } = useTranslation();
  const location = useLocation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => (await api.get<Health>("/health")).data,
    refetchInterval: 15000,
  });
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: async () => (await api.get<SettingsResponse>("/settings")).data,
  });
  const databaseAdminUrl = String(
    settings.data?.values.database_admin_url ?? "http://127.0.0.1:8081",
  );

  const current =
    NAV.find((item) =>
      item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
    ) ?? NAV[0];
  const healthOk = health.data?.status === "ok";

  return (
    <div className="flex min-h-svh">
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-card/40 md:flex">
        <div className="flex h-16 items-center gap-2 border-b px-5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            A
          </span>
          <div>
            <div className="text-sm font-semibold leading-none">{t("app.title")}</div>
            <div className="mt-1 text-[11px] text-muted-foreground">{t("app.tagline")}</div>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  )
                }
              >
                <Icon className="size-4" />
                {t(item.labelKey)}
              </NavLink>
            );
          })}
          <a
            href={databaseAdminUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground"
          >
            <Database className="size-4" />
            {t("nav.database")}
          </a>
        </nav>
        <div className="border-t p-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "size-2 rounded-full",
                healthOk ? "bg-emerald-500" : "bg-amber-500",
              )}
            />
            {healthOk ? "Backend healthy" : "Backend degraded"}
          </div>
          <div className="mt-1">Aura MVP</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur md:px-8">
          <div className="md:hidden">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              A
            </span>
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold">{t(current.labelKey)}</h1>
          </div>
          <div className="ml-auto flex items-center gap-1">
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </header>

        <nav className="flex gap-1 overflow-x-auto border-b px-3 py-2 md:hidden">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-md px-3 py-1.5 text-xs",
                  isActive ? "bg-accent font-medium" : "text-muted-foreground",
                )
              }
            >
              {t(item.labelKey)}
            </NavLink>
          ))}
          <a
            href={databaseAdminUrl}
            target="_blank"
            rel="noreferrer"
            className="whitespace-nowrap rounded-md px-3 py-1.5 text-xs text-muted-foreground"
          >
            {t("nav.database")}
          </a>
        </nav>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
