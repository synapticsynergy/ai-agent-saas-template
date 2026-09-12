#!/usr/bin/env bash
# Deploy the Next.js application.
#
# The template does not pick a web host for you: Next.js deploys well to
# Vercel, AWS Amplify, ECS/Fargate, or a container platform of your choice, and
# the right answer depends on the downstream product. Wire your host here.
ENV_NAME="${1:?usage: web.sh <env>}"
source "$(dirname "$0")/_shared.sh"

if [ -z "${WEB_DEPLOY_COMMAND:-}" ]; then
  cat >&2 <<MSG
ERROR: no web deploy target is configured for '$ENV_NAME'.

The template intentionally leaves the web host unchosen. Pick one and either:

  1. set WEB_DEPLOY_COMMAND in the environment / GitHub Environment secrets, e.g.
       WEB_DEPLOY_COMMAND="pnpm --filter web exec vercel deploy --prod"
  2. or replace the body of scripts/deploy/web.sh with your host's deploy steps.

Terraform outputs available to the command:
  API_BASE_URL   $(tf_output api_base_url)
  AGENT_BASE_URL \${AGENT_BASE_URL:-<from agentcore status>}

See docs/DEPLOYMENT.md ("Web deployment").
MSG
  exit 1
fi

export API_BASE_URL="$(tf_output api_base_url)"
export NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL"

echo "==> $WEB_DEPLOY_COMMAND"
eval "$WEB_DEPLOY_COMMAND"
echo "web deployed to $ENV_NAME"
