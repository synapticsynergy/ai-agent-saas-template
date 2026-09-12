output "base_url" {
  description = "Public base URL of the API."
  value       = aws_apigatewayv2_stage.this.invoke_url
}

output "lambda_function_name" {
  description = "Function name, used by `make api-deploy`."
  value       = aws_lambda_function.this.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.this.arn
}

output "lambda_role_arn" {
  value = aws_iam_role.this.arn
}

output "ecr_repository_url" {
  description = "ECR repository the deploy pipeline pushes to."
  value       = aws_ecr_repository.this.repository_url
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.this.name
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}
