variable "project" {
  type        = string
  description = "Resource name prefix. Change this when adopting the template."
  default     = "ai-agent-saas"
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "vpc_cidr" {
  type    = string
  default = "10.10.0.0/16"
}

variable "workos_client_id" {
  type        = string
  description = "WorkOS client id for the dev environment."
  default     = ""
}

variable "cors_origins" {
  type        = string
  description = "Comma-separated browser origins allowed to call the API."
  default     = "http://localhost:3000"
}

# --- dev sizing: cheapest that still exercises the real services ------------

variable "database_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "database_multi_az" {
  type    = bool
  default = false
}

variable "database_backup_retention_days" {
  type    = number
  default = 1
}

variable "database_deletion_protection" {
  type    = bool
  default = false
}

variable "api_memory_size" {
  type    = number
  default = 512
}

variable "dynamodb_enabled" {
  type    = bool
  default = false
}

variable "log_level" {
  type    = string
  default = "DEBUG"
}

variable "log_retention_days" {
  type    = number
  default = 7
}

variable "places_provider" {
  type    = string
  default = "fixture"
}

variable "events_provider" {
  type    = string
  default = "fixture"
}
