# ADR-006: AgentCore Resources Are Not Managed by Terraform

**Status:** Accepted

## Context

Terraform owns the conventional AWS infrastructure for this template: API
Gateway, Lambda, IAM, S3, RDS, DynamoDB, CloudWatch. The obvious instinct is to
have it own everything, including the Bedrock AgentCore Runtime that hosts the
agent.

The deployment documentation anticipates the tension: "Avoid forcing one IaC
tool to own a resource if the platform's supported deployment path is materially
better," and "Document ownership explicitly so resources are not managed by two
deployment systems."

## Decision

AgentCore Runtime resources are owned by the AgentCore CLI
(`bedrock-agentcore-starter-toolkit`), not by Terraform.

Terraform and AgentCore exchange values explicitly through environment
configuration in `scripts/deploy/agent.sh`: Terraform outputs the API base URL,
the MCP endpoint and the storage bucket; the deploy script reads them and passes
them to `agentcore deploy`.

The same principle applies to AgentCore Gateway when one is used: it fronts the
MCP Lambda that Terraform *does* own, but the Gateway itself is configured
through AgentCore tooling.

## Consequences

Positive:

- one system owns each resource, so there is no drift and no fight over state,
- the AgentCore deployment path stays on its supported track as the platform
  evolves,
- agent releases do not require a Terraform apply.

Negative:

- infrastructure is described in two places, and someone reading only the
  Terraform will not see the whole system,
- the handoff between the two is a script rather than a declarative dependency,
  so a Terraform apply that changes the API URL requires an agent redeploy to
  take effect,
- rollback is per-system rather than a single revert.

## Note

When Terraform gains stable, first-class resource support for AgentCore Runtime,
revisit this. The reason for the split is the maturity of the provider support,
not a belief that two deployment systems is a good end state.
