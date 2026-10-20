import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import { createI18n } from "@/i18n/createI18n";
import "@/styles/index.css";

createI18n();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
