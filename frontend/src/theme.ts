import { useEffect, useState } from "react";

// "system" follows the OS setting; the choice is remembered per browser.
export type ThemeChoice = "system" | "light" | "dark";

const KEY = "theme";
const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

export function storedTheme(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    // Storage blocked (private mode etc.): fall back to the system setting.
  }
  return "system";
}

function apply(choice: ThemeChoice) {
  const resolved = choice === "system" ? (darkQuery.matches ? "dark" : "light") : choice;
  document.documentElement.dataset.theme = resolved;
}

export function useTheme() {
  const [choice, setChoice] = useState<ThemeChoice>(storedTheme);

  useEffect(() => {
    apply(choice);
    try {
      if (choice === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {
      // Not persisted; the choice still applies for this session.
    }
    if (choice !== "system") return;
    const onChange = () => apply("system");
    darkQuery.addEventListener("change", onChange);
    return () => darkQuery.removeEventListener("change", onChange);
  }, [choice]);

  return [choice, setChoice] as const;
}
