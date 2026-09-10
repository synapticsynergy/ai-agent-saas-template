import type { Metadata, Viewport } from "next";

import { ThemeRegistry } from "@/theme/ThemeRegistry";

export const metadata: Metadata = {
  title: {
    default: "Plan My Evening",
    template: "%s · Plan My Evening",
  },
  description: "Reference application for the AI agent SaaS template.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeRegistry>{children}</ThemeRegistry>
      </body>
    </html>
  );
}
