"use client";

import { createTheme } from "@mui/material/styles";

import { LinkBehavior } from "./LinkBehavior";

/**
 * Central theme.
 *
 * Everything visual should be expressed here rather than as per-component
 * overrides or ad hoc CSS, so a downstream product can rebrand the template by
 * editing this one file.
 *
 * It is deliberately neutral: a restrained neutral palette with a single accent,
 * so it reads as a starting point rather than as somebody else's product.
 */

const ACCENT = "#3d5afe";

export const theme = createTheme({
  cssVariables: {
    colorSchemeSelector: "class",
  },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: ACCENT },
        background: { default: "#fafafa", paper: "#ffffff" },
      },
    },
    dark: {
      palette: {
        primary: { main: "#8c9eff" },
        background: { default: "#101215", paper: "#181b1f" },
      },
    },
  },

  shape: { borderRadius: 10 },

  typography: {
    fontFamily: "var(--font-sans, system-ui), -apple-system, Segoe UI, Roboto, sans-serif",
    h1: { fontSize: "2.25rem", fontWeight: 600, letterSpacing: "-0.02em" },
    h2: { fontSize: "1.75rem", fontWeight: 600, letterSpacing: "-0.015em" },
    h3: { fontSize: "1.375rem", fontWeight: 600 },
    h4: { fontSize: "1.125rem", fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },

  components: {
    // Component defaults belong here, not repeated at every call site.

    // Route MUI's `href` through the Next.js router everywhere at once.
    MuiButtonBase: {
      defaultProps: { LinkComponent: LinkBehavior },
    },
    MuiLink: {
      defaultProps: { component: LinkBehavior },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: ({ theme }) => ({
          border: `1px solid ${theme.palette.divider}`,
        }),
      },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: ({ theme }) => ({
          border: `1px solid ${theme.palette.divider}`,
        }),
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0, color: "inherit" },
      styleOverrides: {
        root: ({ theme }) => ({
          borderBottom: `1px solid ${theme.palette.divider}`,
          backgroundImage: "none",
        }),
      },
    },
    MuiChip: {
      defaultProps: { size: "small" },
    },
    MuiTextField: {
      defaultProps: { size: "small" },
    },
    MuiAlert: {
      defaultProps: { variant: "outlined" },
    },
  },
});

export default theme;
