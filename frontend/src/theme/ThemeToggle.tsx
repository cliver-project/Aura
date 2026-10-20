import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { useTheme, type ThemeMode } from "@/theme/ThemeProvider";

const OPTIONS: { value: ThemeMode; icon: typeof Sun }[] = [
  { value: "light", icon: Sun },
  { value: "dark", icon: Moon },
  { value: "system", icon: Monitor },
];

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { t } = useTranslation();
  const ActiveIcon = theme === "system" ? Monitor : resolvedTheme === "dark" ? Moon : Sun;

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={t("theme.label")}
      title={t("theme.label")}
      onClick={() => {
        const index = OPTIONS.findIndex((option) => option.value === theme);
        setTheme(OPTIONS[(index + 1) % OPTIONS.length].value);
      }}
    >
      <ActiveIcon className="size-4" />
    </Button>
  );
}
