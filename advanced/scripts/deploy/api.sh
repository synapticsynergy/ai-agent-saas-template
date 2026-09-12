#!/usr/bin/env bash
# Deploy the FastAPI service as a Lambda container image.
# Terraform owns the Lambda function, ECR repository, API Gateway and IAM.
# This script only publishes a new image and points the function at it.
ENV_NAME="${1:?usage: api.sh <env>}"
source "$(dirname "$0")/_shared.sh"

require aws "Install the AWS CLI: https://aws.amazon.com/cli/"
require docker
require terraform

AWS_REGION="${AWS_REGION:-us-west-2}"
REPO_URL="$(tf_output api_ecr_repository_url)"
FUNCTION_NAME="$(tf_output api_lambda_function_name)"

if [ -z "$REPO_URL" ] || [ -z "$FUNCTION_NAME" ]; then
  echo "ERROR: Terraform outputs for '$ENV_NAME' are missing." >&2
  echo "       Run 'make terraform-apply ENV=$ENV_NAME' before deploying the API." >&2
  exit 1
fi

TAG="$(image_tag)"
build_push_lambda_image api services/api/Dockerfile "$REPO_URL" "$TAG"

echo "==> running database migrations"
./scripts/deploy/migrate.sh "$ENV_NAME"

echo "==> updating $FUNCTION_NAME"
aws lambda update-function-code \
  --region "$AWS_REGION" \
  --function-name "$FUNCTION_NAME" \
  --image-uri "$REPO_URL:$TAG" \
  --publish >/dev/null
aws lambda wait function-updated --region "$AWS_REGION" --function-name "$FUNCTION_NAME"

echo "api deployed to $ENV_NAME ($TAG)"
