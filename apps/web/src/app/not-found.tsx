import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function NotFound() {
  return (
    <Container maxWidth="sm" sx={{ py: { xs: 6, md: 10 } }}>
      <Stack spacing={2} sx={{ alignItems: "flex-start" }}>
        <Typography variant="h2">Not found</Typography>
        <Typography variant="body1" color="text.secondary">
          That page does not exist.
        </Typography>
        <Button href="/" variant="contained">
          Go home
        </Button>
      </Stack>
    </Container>
  );
}
