import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";

export default function AppLoading() {
  return (
    <Stack spacing={2} sx={{ py: 2 }} aria-busy="true">
      <Skeleton variant="text" width={220} height={40} />
      <Skeleton variant="rounded" height={120} />
      <Skeleton variant="rounded" height={320} />
    </Stack>
  );
}
