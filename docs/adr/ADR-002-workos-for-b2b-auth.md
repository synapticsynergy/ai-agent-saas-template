# ADR-002: Use WorkOS for B2B Authentication and RBAC

**Status:** Accepted

## Context

The starter should demonstrate enterprise-quality SaaS identity without spending most of the implementation on authentication plumbing.

## Decision

Use WorkOS AuthKit for authentication, organizations, memberships, roles, and permissions.

Application authorization code depends on generic permission claims such as:

```text
plans:read
plans:write
agents:run
```

rather than hard-coding WorkOS concepts throughout domain services.

## Consequences

Positive:

- low implementation scope,
- strong B2B SaaS signal,
- organization-aware sessions,
- enterprise SSO/Directory Sync upgrade path.

Negative:

- managed provider dependency,
- local development still depends on WorkOS development configuration.
