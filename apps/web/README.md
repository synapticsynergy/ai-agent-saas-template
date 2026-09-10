# Web application

Next.js App Router, Material UI, CopilotKit and WorkOS AuthKit.

## Design system

Material UI is the only component and styling system. Everything visual lives in
`src/theme/theme.ts` — palette, typography, shape, component defaults — so a
downstream product rebrands by editing one file.

Two conventions worth knowing:

- **Layout goes in `sx`.** MUI v9 removed system props from components, so
  `alignItems` and friends are `sx={{ alignItems: "center" }}`.
- **Links use `href`, not `component={NextLink}`.** A Server Component cannot
  pass a function to a Client Component, so a `LinkBehavior` is registered on
  `MuiButtonBase` and `MuiLink` in the theme. Server-rendered pages just write
  `<Button href="/plans">` and still get client-side navigation.

## Structure

```text
src/
├── app/
│   ├── (app)/            protected route group; the layout enforces the session
│   ├── api/copilotkit/   the agent runtime endpoint and identity boundary
│   ├── auth/callback/    WorkOS AuthKit redirect URI
│   └── page.tsx
├── components/           AppShell, PlannerView, ItineraryPanel, ItineraryMap
├── hooks/                usePlannerAgent, useAgentProgress
├── lib/                  auth, api, env, itinerary, format
├── theme/
└── middleware.ts         AuthKit session refresh
```

## Identity

`src/app/api/copilotkit/[[...path]]/route.ts` is the identity injection
boundary. It reads the verified WorkOS session on the server and attaches the
access token to the agent request. The browser never holds a bearer token, and
agents are built per request so a token is never captured in a shared instance.

`src/lib/auth.ts` exposes `hasPermission` for deciding what to *offer*. That is
a usability choice, not a security control — the API enforces the same
permissions regardless of what the UI rendered.

## Local development without WorkOS

Set `AUTH_DEV_FIXTURE=1` and `APP_ENV=local`. The app then uses a deterministic
fixture identity and the middleware steps aside. Both the app and the API refuse
to start with the flag set outside `APP_ENV=local`, so it cannot leak into a
deployed environment.

## Configuration

Configuration comes from the repository-root `.env`, loaded explicitly by
`next.config.ts` because Next only reads its own directory by default. Values
already in the environment win.

## Commands

```bash
pnpm dev
pnpm build
pnpm lint
pnpm typecheck
pnpm test
```
