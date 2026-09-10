# Local environment, applied against LocalStack.
#
# Only the conventional AWS resources LocalStack reproduces faithfully: object
# storage and the optional DynamoDB table. There is deliberately no Lambda,
# API Gateway, RDS or VPC here — locally those run as processes and containers,
# and emulating them would create false parity without improving the dev loop
# (docs/adr/ADR-004).
#
# Applying this is optional and exists so the Terraform itself can be exercised
# locally. It deliberately creates *separately named* resources from the ones
# `make infra-up` bootstraps: two systems managing one resource is the failure
# the deployment docs warn about, and it shows up immediately as a
# "table already exists" apply error.
#
# The running application uses the bootstrapped resources; this environment
# proves the modules apply.
#
#   make infra-local-apply

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region                      = var.region
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3       = var.localstack_endpoint
    dynamodb = var.localstack_endpoint
    iam      = var.localstack_endpoint
    sts      = var.localstack_endpoint
    logs     = var.localstack_endpoint
  }
}

locals {
  # Not plain "local": these resources exist alongside the ones the compose
  # bootstrap creates, and must not collide with them.
  environment = "local-tf"

  tags = {
    Project     = var.project
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}

module "storage" {
  source = "../../modules/storage"

  project       = var.project
  environment   = local.environment
  bucket_suffix = "localstack"

  # Versioning and lifecycle rules add nothing locally and are slower to apply.
  versioning_enabled = false
  dynamodb_enabled   = var.dynamodb_enabled

  tags = local.tags
}
