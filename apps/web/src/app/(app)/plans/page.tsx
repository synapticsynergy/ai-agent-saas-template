import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { Metadata } from "next";

import { ApiError, listPlans } from "@/lib/api";
import { requireSession } from "@/lib/auth";

export const metadata: Metadata = { title: "Saved plans" };
export const dynamic = "force-dynamic";

/**
 * Saved plans, read through the deterministic API.
 *
 * Deliberately does not involve the agent: a saved plan is application data and
 * must be retrievable without an agent run.
 */
export default async function PlansPage() {
  await requireSession();

  let plans;
  try {
    plans = await listPlans();
  } catch (error) {
    const message =
      error instanceof ApiError
        ? `${error.message} (${error.code})`
        : "The application API is unreachable. Is it running? Try `make infra-up && make dev`.";
    return <Alert severity="error">{message}</Alert>;
  }

  return (
    <Stack spacing={{ xs: 2, md: 3 }}>
      <Stack direction="row" spacing={2} sx={{ alignItems: "center" }}>
        <Typography variant="h2" sx={{ flexGrow: 1 }}>
          Saved plans
        </Typography>
        <Button href="/planner" variant="contained">
          New plan
        </Button>
      </Stack>

      {plans.items.length === 0 ? (
        <Alert severity="info">
          Nothing saved yet. Plan an evening and ask the assistant to save it.
        </Alert>
      ) : (
        <Box
          sx={{
            display: "grid",
            gap: 2,
            gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" },
          }}
        >
          {plans.items.map((plan) => (
            <Card key={plan.id}>
              <CardContent>
                <Stack spacing={1}>
                  <Typography variant="subtitle2">{plan.title}</Typography>
                  <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
                    <Chip label={`$${Math.round(plan.estimated_cost ?? 0)}`} />
                    <Chip label={`${plan.stops?.length ?? 0} stops`} />
                    <Chip variant="outlined" label={plan.status} />
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(plan.start_time).toLocaleString()}
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
    </Stack>
  );
}
