# ADR-004: Use LocalStack Selectively

**Status:** Superseded for the default path by [ADR-010](ADR-010-railway-and-vercel.md); still applies under `advanced/`

## Context

Local cloud emulation can shorten development and CI loops, but attempting to reproduce every managed AWS service locally creates false parity and unnecessary complexity.

## Decision

Use LocalStack for conventional AWS services where local emulation materially improves development and integration testing, including S3, DynamoDB, Lambda, API Gateway, and messaging services when added.

The agent needs nothing from LocalStack: it runs as an ordinary local process
alongside the API and the MCP server (ADR-009), and `AGENT_MODEL_PROVIDER=scripted`
removes the model call entirely, so the whole stack runs with no cloud
credentials of any kind.

## Consequences

Positive:

- fast AWS integration tests,
- lower development friction,
- IaC can be exercised locally,
- clean responsibility boundary.

Negative:

- local is not perfect cloud parity,
- some integration behavior still requires dev/staging cloud tests.
