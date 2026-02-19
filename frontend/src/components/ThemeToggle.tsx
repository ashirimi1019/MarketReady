"use client";

import { useEffect, useMemo } from "react";
import { useLocalStorage } from "@/lib/useLocalStorage";

type ThemeMode = "dark" | "light";

const STORAGE_KEY = "mp-theme-mode";

export default function ThemeToggle() {
  const [theme, setTheme] = useLocalStorage(STORAGE_KEY, "dark");

  useEffect(() => {
    if (theme !== "dark" && theme !== "light") {
      const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
      setTheme(prefersLight ? "light" : "dark");
      return;
    }
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme;
  }, [theme, setTheme]);

  const currentTheme = useMemo<ThemeMode>(
    () => (theme === "light" ? "light" : "dark"),
    [theme]
  );
  const nextTheme: ThemeMode = currentTheme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="nav-pill nav-pill-theme"
      aria-label={`Switch to ${nextTheme} mode`}
      onClick={() => setTheme(nextTheme)}
    >
      <span className="theme-indicator" aria-hidden />
      {currentTheme === "dark" ? "Dark" : "Light"}
    </button>
  );
}

