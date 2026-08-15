"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

// next-themes applies the `.dark` class to <html> and persists the choice.
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
