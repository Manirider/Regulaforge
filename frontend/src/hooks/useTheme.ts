import { useEffect } from "react";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { setTheme, toggleTheme } from "@/stores/uiSlice";

export function useTheme() {
  const dispatch = useAppDispatch();
  const theme = useAppSelector((s) => s.ui.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return {
    theme,
    isDark: theme === "dark",
    toggle: () => dispatch(toggleTheme()),
    setTheme: (t: "dark" | "light") => dispatch(setTheme(t)),
  };
}
