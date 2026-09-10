import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";

export default function Loading() {
  return (
    <Box sx={{ display: "grid", placeItems: "center", minHeight: "50dvh" }} aria-busy="true">
      <CircularProgress />
    </Box>
  );
}
