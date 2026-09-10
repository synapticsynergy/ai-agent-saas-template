"use client";

import NextLink, { type LinkProps as NextLinkProps } from "next/link";
import { forwardRef } from "react";

/**
 * Makes MUI's `href` prop use the Next.js router.
 *
 * Registered globally in the theme rather than written at each call site,
 * because `component={NextLink}` cannot cross the server/client boundary: a
 * Server Component may not pass a function as a prop to a Client Component.
 * With this, server-rendered pages just write `<Button href="/plans">` and
 * still get client-side navigation.
 */
export const LinkBehavior = forwardRef<
  HTMLAnchorElement,
  Omit<NextLinkProps, "href"> & { href?: NextLinkProps["href"] }
>(function LinkBehavior({ href, ...props }, ref) {
  return <NextLink ref={ref} href={href ?? "#"} {...props} />;
});

export default LinkBehavior;
