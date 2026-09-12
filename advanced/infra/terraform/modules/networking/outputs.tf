output "vpc_id" {
  description = "The VPC id."
  value       = aws_vpc.this.id
}

output "private_subnet_ids" {
  description = "Private subnet ids, for Lambda and the database."
  value       = [for s in aws_subnet.private : s.id]
}

output "public_subnet_ids" {
  description = "Public subnet ids."
  value       = [for s in aws_subnet.public : s.id]
}

output "lambda_security_group_id" {
  description = "Security group for VPC-attached Lambda functions."
  value       = aws_security_group.lambda.id
}

output "database_security_group_id" {
  description = "Security group for the database."
  value       = aws_security_group.database.id
}
