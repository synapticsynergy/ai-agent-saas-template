# Outputs consumed by the deploy scripts (scripts/deploy/*.sh) and by
# `make smoke`. Keep the names stable: they are the contract between Terraform
# and everything that deploys on top of it.

output "api_base_url" {
  description = "Public base URL of the application API."
  value       = module.api.base_url
}

output "api_lambda_function_name" {
  value = module.api.lambda_function_name
}

output "api_ecr_repository_url" {
  value = module.api.ecr_repository_url
}

output "mcp_function_url" {
  description = "MCP endpoint. Append /mcp for the streamable-HTTP path."
  value       = module.mcp.function_url
}

output "mcp_lambda_function_name" {
  value = module.mcp.lambda_function_name
}

output "mcp_ecr_repository_url" {
  value = module.mcp.ecr_repository_url
}

output "storage_bucket_name" {
  value = module.storage.bucket_name
}

output "database_secret_name" {
  description = "Secrets Manager entry holding DATABASE_URL and DATABASE_SYNC_URL."
  value       = module.database.secret_name
}

output "database_endpoint" {
  description = "Database host:port. The credentials live in Secrets Manager."
  value       = module.database.endpoint
}

output "vpc_id" {
  value = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Subnets a migration runner must attach to in order to reach the database."
  value       = module.networking.private_subnet_ids
}

output "lambda_security_group_id" {
  value = module.networking.lambda_security_group_id
}

output "alert_topic_arn" {
  value = module.observability.alert_topic_arn
}

output "dashboard_name" {
  value = module.observability.dashboard_name
}
