import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import MuiLink from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import type { ReactNode } from "react";

import type { Session } from "@/lib/auth";

/**
 * Authenticated application shell.
 *
 * Deliberately plain: a downstream product replaces the brand and navigation
 * here, and everything visual comes from the theme rather than local styling.
 */
export function AppShell({
  session,
  devFixtureAuth = false,
  children,
}: {
  session: Session;
  devFixtureAuth?: boolean;
  children: ReactNode;
}) {
  return (
    <Box sx={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <AppBar position="sticky">
        <Toolbar sx={{ gap: { xs: 0.5, sm: 2 } }}>
          {/* The brand collapses on a phone so navigation always fits. The
              reference app is used while out; hiding the nav behind a
              breakpoint would make saved plans unreachable there. */}
          <MuiLink
            href="/planner"
            variant="h4"
            underline="none"
            noWrap
            sx={{ color: "inherit", display: { xs: "none", sm: "block" }, mr: 1 }}
          >
            Plan My Evening
          </MuiLink>

          <Stack direction="row" spacing={{ xs: 0, sm: 1 }}>
            <Button href="/planner" color="inherit">
              Planner
            </Button>
            <Button href="/plans" color="inherit">
              Plans
            </Button>
          </Stack>

          <Box sx={{ flexGrow: 1 }} />

          {devFixtureAuth ? (
            <Tooltip title="AUTH_DEV_FIXTURE is enabled. Local development only — the API and web app both refuse to start with this outside APP_ENV=local.">
              <Chip color="warning" label="Fixture auth" />
            </Tooltip>
          ) : null}

          <Tooltip title={`Organization ${session.organizationId} · role ${session.role || "—"}`}>
            <Chip
              variant="outlined"
              label={session.email || session.userId}
              sx={{ display: { xs: "none", md: "inline-flex" }, maxWidth: 260 }}
            />
          </Tooltip>

          <Button href="/logout" color="inherit">
            Sign out
          </Button>
        </Toolbar>
      </AppBar>

      <Container
        maxWidth="xl"
        component="main"
        sx={{ flexGrow: 1, px: { xs: 2, md: 4 }, py: { xs: 2, md: 3 } }}
      >
        {children}
      </Container>
    </Box>
  );
}

export default AppShell;
