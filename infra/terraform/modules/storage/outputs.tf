output "bucket_name" {
  description = "Application object storage bucket."
  value       = aws_s3_bucket.this.id
}

output "bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "dynamodb_table_name" {
  description = "DynamoDB table name, or an empty string when disabled."
  value       = var.dynamodb_enabled ? aws_dynamodb_table.this[0].name : ""
}

output "dynamodb_table_arn" {
  value = var.dynamodb_enabled ? aws_dynamodb_table.this[0].arn : ""
}
