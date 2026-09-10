# ADR-004: Use LocalStack Selectively

**Status:** Accepted

## Context

Local cloud emulation can shorten development and CI loops, but attempting to reproduce every managed AWS service locally creates false parity and unnecessary complexity.

## Decision

Use LocalStack for conventional AWS services where local emulation materially improves development and integration testing, including S3, DynamoDB, Lambda, API Gateway, and messaging services when added.

Use AgentCore's supported local development workflow for the agent runtime.

## Consequences

Positive:

- fast AWS integration tests,
- lower development friction,
- IaC can be exercised locally,
- clean responsibility boundary.

Negative:

- local is not perfect cloud parity,
- some integration behavior still requires dev/staging cloud tests.
