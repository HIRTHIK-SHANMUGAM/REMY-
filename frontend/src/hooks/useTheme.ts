import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

/**
 * Theme is applied pre-paint by an inline script in index.html (reading
 * localStorage → OS preference). This hook exposes the current value and a
 * toggle that persists the choice; it also follows OS changes until the user
 * makes an explicit choice.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(currentTheme);

  const apply = useCallback((t: Theme) => {
    document.documentElement.classList.toggle("dark", t === "dark");
    setThemeState(t);
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    localStorage.setItem("remy-theme", next);
    apply(next);
  }, [theme, apply]);

  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      // Only follow the OS if the user hasn't picked a theme explicitly.
      if (!localStorage.getItem("remy-theme")) apply(e.matches ? "dark" : "light");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [apply]);

  return { theme, toggle };
}
