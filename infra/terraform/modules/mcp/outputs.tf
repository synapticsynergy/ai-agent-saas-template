output "function_url" {
  description = "MCP streamable-HTTP endpoint. Append /mcp for the transport path."
  value       = aws_lambda_function_url.this.function_url
}

output "lambda_function_name" {
  value = aws_lambda_function.this.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.this.arn
}

output "lambda_role_arn" {
  value = aws_iam_role.this.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.this.repository_url
}
