import { ThemeChoice, useTheme } from "../theme";

const NEXT: Record<ThemeChoice, ThemeChoice> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemeChoice, string> = { system: "◐ System", light: "☀ Light", dark: "☾ Dark" };

export default function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  return (
    <button
      type="button"
      className="ghost small theme-toggle"
      onClick={() => setTheme(NEXT[theme])}
      title={`Theme: ${theme}. Click to switch to ${NEXT[theme]}.`}
    >
      {LABEL[theme]}
    </button>
  );
}
