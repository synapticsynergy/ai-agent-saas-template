variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnets the function runs in."
}

variable "security_group_id" {
  type        = string
  description = "Security group permitted to reach the database."
}

variable "database_secret_arn" {
  type        = string
  description = "Secrets Manager ARN holding the connection strings."
}

variable "database_secret_name" {
  type        = string
  description = "Secrets Manager name, passed to the function as configuration."
}

variable "storage_bucket_name" {
  type = string
}

variable "storage_bucket_arn" {
  type = string
}

variable "dynamodb_table_name" {
  type    = string
  default = ""
}

variable "dynamodb_table_arn" {
  type        = string
  description = "Empty string disables the DynamoDB grant entirely."
  default     = ""
}

variable "workos_client_id" {
  type        = string
  description = <<-EOT
    WorkOS client id. Public by design — it only identifies which JWKS to verify
    access tokens against. The API key is never given to this function; the API
    verifies tokens, it does not call WorkOS.
  EOT
  default     = ""
}

variable "cors_origins" {
  type        = string
  description = "Comma-separated list of allowed browser origins."
}

variable "image_uri" {
  type        = string
  description = "Initial image. Left empty on first apply; the deploy pipeline sets it thereafter."
  default     = ""
}

variable "image_retention_count" {
  type        = number
  description = "How many images to keep in ECR."
  default     = 20
}

variable "memory_size" {
  type    = number
  default = 512
}

variable "timeout_seconds" {
  type    = number
  default = 30
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "throttling_burst_limit" {
  type    = number
  default = 200
}

variable "throttling_rate_limit" {
  type    = number
  default = 100
}

variable "extra_environment" {
  type        = map(string)
  description = "Additional environment variables. Never put a secret here — it would be visible in the function configuration."
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
