"use client";

import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useEffect } from "react";

/**
 * Application error boundary.
 *
 * Shows the message rather than a generic apology: in this template the most
 * likely errors are configuration problems, and their messages say exactly what
 * to fix.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <Container maxWidth="sm" sx={{ py: { xs: 6, md: 10 } }}>
      <Stack spacing={3}>
        <Alert severity="error">
          <AlertTitle>Something went wrong</AlertTitle>
          <Typography variant="body2" component="pre" sx={{ whiteSpace: "pre-wrap", m: 0 }}>
            {error.message}
          </Typography>
        </Alert>
        <Button onClick={reset} variant="contained" sx={{ alignSelf: "flex-start" }}>
          Try again
        </Button>
      </Stack>
    </Container>
  );
}
