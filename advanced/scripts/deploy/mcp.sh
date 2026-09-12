#!/usr/bin/env bash
# Deploy the MCP server as a Lambda container image behind a Function URL.
# When AGENTCORE_GATEWAY_URL is configured for the environment, the Gateway
# fronts this deployment as an MCP target; the Gateway itself is owned by the
# AgentCore tooling, not Terraform (see docs/adr/ADR-006).
ENV_NAME="${1:?usage: mcp.sh <env>}"
source "$(dirname "$0")/_shared.sh"

require aws "Install the AWS CLI: https://aws.amazon.com/cli/"
require docker
require terraform

AWS_REGION="${AWS_REGION:-us-west-2}"
REPO_URL="$(tf_output mcp_ecr_repository_url)"
FUNCTION_NAME="$(tf_output mcp_lambda_function_name)"

if [ -z "$REPO_URL" ] || [ -z "$FUNCTION_NAME" ]; then
  echo "ERROR: Terraform outputs for '$ENV_NAME' are missing." >&2
  echo "       Run 'make terraform-apply ENV=$ENV_NAME' before deploying the MCP server." >&2
  exit 1
fi

TAG="$(image_tag)"
build_push_lambda_image mcp services/mcp/Dockerfile "$REPO_URL" "$TAG"

echo "==> updating $FUNCTION_NAME"
aws lambda update-function-code \
  --region "$AWS_REGION" \
  --function-name "$FUNCTION_NAME" \
  --image-uri "$REPO_URL:$TAG" \
  --publish >/dev/null
aws lambda wait function-updated --region "$AWS_REGION" --function-name "$FUNCTION_NAME"

echo "mcp deployed to $ENV_NAME ($TAG)"
