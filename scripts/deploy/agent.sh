#!/usr/bin/env bash
# Deploy the Strands agent to Bedrock AgentCore Runtime.
#
# AgentCore Runtime resources are owned by the AgentCore CLI, not Terraform
# (see docs/adr/ADR-006). Terraform outputs are passed in as environment
# configuration so the two systems exchange values explicitly.
ENV_NAME="${1:?usage: agent.sh <env>}"
source "$(dirname "$0")/_shared.sh"

require agentcore "Install with: uv tool install bedrock-agentcore-starter-toolkit"
require terraform

AGENT_NAME="ai_agent_saas_${ENV_NAME}"

export API_BASE_URL="$(tf_output api_base_url)"
export MCP_SERVER_URL="${MCP_SERVER_URL:-$(tf_output mcp_function_url)}"
export S3_BUCKET="$(tf_output storage_bucket_name)"

if [ -z "$API_BASE_URL" ]; then
  echo "ERROR: Terraform outputs for '$ENV_NAME' are missing." >&2
  echo "       Run 'make terraform-apply ENV=$ENV_NAME' before deploying the agent." >&2
  exit 1
fi

cd services/agent

echo "==> agentcore configure ($AGENT_NAME)"
agentcore configure --entrypoint agent.py --name "$AGENT_NAME" --non-interactive

echo "==> agentcore deploy --dry-run"
agentcore deploy --dry-run

echo "==> agentcore deploy"
agentcore deploy

agentcore status
echo "agent deployed to $ENV_NAME"
