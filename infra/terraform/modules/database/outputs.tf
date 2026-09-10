output "endpoint" {
  description = "Database endpoint host:port."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "Database hostname."
  value       = aws_db_instance.this.address
}

output "database_name" {
  description = "Initial database name."
  value       = aws_db_instance.this.db_name
}

output "secret_arn" {
  description = "Secrets Manager ARN holding DATABASE_URL and DATABASE_SYNC_URL."
  value       = aws_secretsmanager_secret.database_url.arn
}

output "secret_name" {
  description = "Secrets Manager name holding the connection strings."
  value       = aws_secretsmanager_secret.database_url.name
}
