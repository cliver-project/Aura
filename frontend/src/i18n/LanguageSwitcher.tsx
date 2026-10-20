import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
] as const;

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const current = i18n.language?.startsWith("zh") ? "zh" : "en";
  const next = current === "en" ? LANGUAGES[1] : LANGUAGES[0];

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={t("language.label")}
      title={next.label}
      onClick={() => void i18n.changeLanguage(next.code)}
    >
      <Languages className="size-4" />
    </Button>
  );
}
