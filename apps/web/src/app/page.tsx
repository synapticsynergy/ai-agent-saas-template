import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { getSession } from "@/lib/auth";

const CAPABILITIES = [
  ["Streaming agent", "Tool activity and itinerary state stream as they happen."],
  ["Tenant isolation", "Every record is scoped to a WorkOS organization."],
  ["Permission checks", "Authorization is enforced in deterministic code."],
  ["MCP tools", "Capabilities are reachable over a portable protocol."],
];

export default async function HomePage() {
  const session = await getSession();

  return (
    <Container maxWidth="md" sx={{ py: { xs: 6, md: 12 } }}>
      <Stack spacing={{ xs: 4, md: 6 }}>
        <Stack spacing={2}>
          <Chip label="Reference application" sx={{ alignSelf: "flex-start" }} />
          <Typography variant="h1">Plan my evening</Typography>
          <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 620 }}>
            Describe the evening you want. The agent finds places and live events nearby, checks
            that the route is walkable, and builds an itinerary you can revise and save.
          </Typography>
        </Stack>

        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <Button href={session ? "/planner" : "/login"} variant="contained" size="large">
            {session ? "Open the planner" : "Sign in to start"}
          </Button>
          {session ? (
            <Button href="/plans" variant="outlined" size="large">
              Saved plans
            </Button>
          ) : null}
        </Stack>

        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" },
          }}
        >
          {CAPABILITIES.map(([title, description]) => (
            <Paper key={title} sx={{ p: { xs: 2, md: 3 } }}>
              <Typography variant="subtitle2" gutterBottom>
                {title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {description}
              </Typography>
            </Paper>
          ))}
        </Box>
      </Stack>
    </Container>
  );
}
