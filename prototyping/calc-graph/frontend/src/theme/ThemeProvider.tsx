import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type ThemeChoice = "system" | "light" | "dark";
interface ThemeCtx {
  choice: ThemeChoice;
  /** the theme actually showing (system resolved) */
  resolved: "light" | "dark";
  toggle: () => void;
  setChoice: (c: ThemeChoice) => void;
}
const Ctx = createContext<ThemeCtx | null>(null);
const KEY = "cg-theme";

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    /* storage blocked */
  }
  return "system";
}
const systemDark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice);
  const [sysDark, setSysDark] = useState(systemDark);

  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const on = () => setSysDark(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  useEffect(() => {
    const r = document.documentElement;
    if (choice === "system") delete r.dataset.theme;
    else r.dataset.theme = choice;
    try {
      if (choice === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, choice);
    } catch {
      /* storage blocked: theme still applies for this page */
    }
  }, [choice]);

  const resolved: "light" | "dark" = choice === "system" ? (sysDark ? "dark" : "light") : choice;
  const setChoice = useCallback((c: ThemeChoice) => setChoiceState(c), []);
  const toggle = useCallback(() => setChoiceState(resolved === "dark" ? "light" : "dark"), [resolved]);
  return <Ctx.Provider value={{ choice, resolved, toggle, setChoice }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useTheme outside ThemeProvider");
  return c;
}
