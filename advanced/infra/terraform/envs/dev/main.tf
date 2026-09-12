# dev environment.
#
# Composes the shared modules. Every environment has its own state (see
# backend.tf) and its own AWS resources — nothing is shared between them, and
# nothing non-production can reach production data.

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
  region = var.region

  default_tags {
    tags = local.tags
  }
}

data "aws_caller_identity" "current" {}

locals {
  environment = "dev"

  tags = {
    Project     = var.project
    Environment = local.environment
    ManagedBy   = "terraform"
  }
}

module "networking" {
  source = "../../modules/networking"

  project     = var.project
  environment = local.environment
  vpc_cidr    = var.vpc_cidr

  # The API reaches Postgres and WorkOS's JWKS endpoint. JWKS is public
  # internet, so a VPC-attached function needs egress.
  enable_nat_gateway = true

  tags = local.tags
}

module "storage" {
  source = "../../modules/storage"

  project       = var.project
  environment   = local.environment
  bucket_suffix = data.aws_caller_identity.current.account_id

  dynamodb_enabled = var.dynamodb_enabled

  tags = local.tags
}

module "database" {
  source = "../../modules/database"

  project     = var.project
  environment = local.environment

  subnet_ids        = module.networking.private_subnet_ids
  security_group_id = module.networking.database_security_group_id

  instance_class        = var.database_instance_class
  multi_az              = var.database_multi_az
  backup_retention_days = var.database_backup_retention_days
  deletion_protection   = var.database_deletion_protection

  tags = local.tags
}

module "api" {
  source = "../../modules/api"

  project     = var.project
  environment = local.environment

  subnet_ids        = module.networking.private_subnet_ids
  security_group_id = module.networking.lambda_security_group_id

  database_secret_arn  = module.database.secret_arn
  database_secret_name = module.database.secret_name

  storage_bucket_name = module.storage.bucket_name
  storage_bucket_arn  = module.storage.bucket_arn
  dynamodb_table_name = module.storage.dynamodb_table_name
  dynamodb_table_arn  = module.storage.dynamodb_table_arn

  workos_client_id = var.workos_client_id
  cors_origins     = var.cors_origins

  memory_size        = var.api_memory_size
  log_level          = var.log_level
  log_retention_days = var.log_retention_days

  tags = local.tags
}

module "mcp" {
  source = "../../modules/mcp"

  project     = var.project
  environment = local.environment

  api_base_url    = module.api.base_url
  places_provider = var.places_provider
  events_provider = var.events_provider

  log_level          = var.log_level
  log_retention_days = var.log_retention_days

  tags = local.tags
}

module "observability" {
  source = "../../modules/observability"

  project     = var.project
  environment = local.environment
  region      = var.region

  api_function_name  = module.api.lambda_function_name
  api_log_group_name = module.api.log_group_name

  tags = local.tags
}
