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

## The planner surface

The map fills the viewport and the itinerary floats over it. The plan — not the
conversation — is what the person came to look at, so the conversation lives in
CopilotKit's popup: a button in the corner that slides a panel in.

Both surfaces drive the same agent. `CopilotPopup` sends the messages;
`usePlannerAgent` subscribes to the resulting AG-UI events and projects them
into the map, the cards and the progress list. They share one agent instance
because they name the same `agentId`, so nothing is duplicated and the map
updates while the reply is still streaming.

Mapping is Leaflet with raster tiles — no key, no WebGL, and a legible street
map at the scale an itinerary needs. The tile URL and attribution are
environment variables, so switching providers is configuration.

> The default tiles come from OpenStreetMap's public server. Its usage policy
> forbids production traffic; point `NEXT_PUBLIC_MAP_TILE_URL` at your own
> provider before deploying.

## Route groups

Parenthesised folders are Next.js *route groups*: they organise files without
adding a URL segment, so `(map)/planner/` serves `/planner`.

There are two, and the only thing separating them is the shell: the planner
needs the whole viewport for its map, Plans wants a normal padded page, and a
layout cannot vary a prop per child route. Each group's layout is also the
authentication boundary for the pages beneath it — `requireSession()` runs
before any of them render.

## Structure

```text
src/
├── app/
│   ├── (map)/planner/        full-bleed: the map owns the viewport
│   ├── (standard)/plans/     normal padded page
│   ├── api/copilotkit/       the agent runtime endpoint and identity boundary
│   ├── auth/callback/        WorkOS AuthKit redirect URI
│   └── page.tsx
├── components/
│   ├── AppShell             app bar; `fullBleed` for map pages
│   ├── PlannerSurface       client-only boundary (Leaflet needs `window`)
│   ├── PlannerView          map + overlay + popup + approval
│   ├── ItineraryOverlay     the floating header and stop cards
│   └── ItineraryMap         Leaflet, numbered markers, route line
├── hooks/                   usePlannerAgent, useAgentProgress
├── lib/                     auth, api, env, itinerary, format
├── theme/
└── middleware.ts            AuthKit session refresh
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
