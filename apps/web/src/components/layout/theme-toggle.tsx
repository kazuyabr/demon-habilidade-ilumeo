"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // mount-only flag to avoid hydration mismatch between server and client theme
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground">
        <Sun className="mr-2 h-4 w-4" />
        Tema
      </Button>
    );
  }

  const dark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="sm"
      className="w-full justify-start text-muted-foreground"
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun className="mr-2 h-4 w-4" /> : <Moon className="mr-2 h-4 w-4" />}
      {dark ? "Claro" : "Escuro"}
    </Button>
  );
}
