# Application API

FastAPI on Lambda. Owns deterministic behaviour: persistence, tenancy,
authorization. It deliberately does not proxy the agent stream
([ADR-001](../../docs/adr/ADR-001-separate-api-and-agent-runtime.md)).

## Where authorization lives

`app/auth/permissions.py` defines one primitive:

```python
require_permission(principal, "plans:write")
```

Application code authorizes on permission slugs, never on role names. Roles are
just a convenient way to assign a permission set in WorkOS; adding one must
never require touching authorization logic.

Checks happen in two places, deliberately:

- **Routes** give an early, cheap 403.
- **Services** re-check, so a caller arriving another way — an MCP tool, a
  background job, a test — cannot bypass it by forgetting a decorator.

## Tenancy

Every service function takes a `Principal` and derives `organization_id` from
it. No function accepts an `organization_id` parameter, and no create or update
schema has the field. A model that invents one has nowhere to put it: the value
is dropped at validation.

A plan belonging to another organization raises `NotFound`, not
`PermissionDenied` — a 403 would confirm the id exists.

## Identity

The API never sees a WorkOS session cookie. Callers forward the AuthKit access
token as `Authorization: Bearer <jwt>`, and `app/auth/workos.py` verifies the
signature against the WorkOS JWKS. Nothing is trusted because of where it came
from.

## Routes

```text
GET    /health              liveness
GET    /health/ready        readiness, per-dependency, 503 when degraded
GET    /users/me            the caller's organization, role and permissions
GET    /plans               tenant-scoped list
GET    /plans/{id}          404 across organizations
POST   /plans               requires plans:write; idempotent on a supplied key
PATCH  /plans/{id}          requires plans:write
DELETE /plans/{id}          requires plans:delete
POST   /agent-runs          requires agents:run
POST   /agent-runs/{id}/complete
GET    /agent-runs/{id}
```

Domain exceptions map to HTTP in one place (`app/main.py`), so services never
import `HTTPException` and stay usable from tools and tests.

## Commands

```bash
make api-dev
make db-migrate
make db-migration NAME="add something"
make seed
```
