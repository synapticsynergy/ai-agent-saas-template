#!/usr/bin/env bash
# Runs inside the LocalStack container once it is ready.
# Creates the conventional AWS resources the local stack expects.
set -euo pipefail

BUCKET="${S3_BUCKET:-ai-agent-saas-local}"
REGION="${AWS_REGION:-us-west-2}"

awslocal s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" 2>/dev/null || true

awslocal dynamodb create-table \
  --table-name "${DYNAMODB_TABLE:-ai-agent-saas-local}" \
  --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION" 2>/dev/null || true

echo "localstack bootstrap complete: s3://$BUCKET"
