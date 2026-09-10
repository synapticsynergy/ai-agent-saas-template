"use client";

import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v16-appRouter";
import type { ReactNode } from "react";

import theme from "./theme";

/**
 * Emotion cache + theme for the App Router.
 *
 * `AppRouterCacheProvider` inserts Emotion's styles during the server render so
 * the first paint is already styled — without it, MUI content flashes unstyled.
 */
export function ThemeRegistry({ children }: { children: ReactNode }) {
  return (
    <AppRouterCacheProvider options={{ key: "mui" }}>
      <ThemeProvider theme={theme} defaultMode="system">
        <CssBaseline enableColorScheme />
        {children}
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}

export default ThemeRegistry;
