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
  default = "10.30.0.0/16"
}

variable "workos_client_id" {
  type        = string
  description = "WorkOS client id for production. Never reuse a non-production environment's."
  default     = ""
}

variable "cors_origins" {
  type        = string
  description = "Comma-separated browser origins allowed to call the API. Never a wildcard."
  default     = ""

  validation {
    condition     = !can(regex("\\*", var.cors_origins))
    error_message = "Production CORS origins must be explicit; a wildcard would let any site call the API with credentials."
  }

  validation {
    condition     = !can(regex("localhost", var.cors_origins))
    error_message = "Production CORS origins must not include localhost."
  }
}

# --- production sizing: durability and availability first -------------------

variable "database_instance_class" {
  type    = string
  default = "db.m7g.large"
}

variable "database_multi_az" {
  type        = bool
  description = "A standby in a second availability zone. Always on in production."
  default     = true

  validation {
    condition     = var.database_multi_az
    error_message = "Production runs multi-AZ."
  }
}

variable "database_backup_retention_days" {
  type    = number
  default = 30

  validation {
    condition     = var.database_backup_retention_days >= 7
    error_message = "Production keeps at least seven days of backups."
  }
}

variable "database_deletion_protection" {
  type        = bool
  description = "Blocks deletion and forces a final snapshot."
  default     = true

  validation {
    condition     = var.database_deletion_protection
    error_message = "Production must not be destroyable by a stray terraform destroy."
  }
}

variable "api_memory_size" {
  type    = number
  default = 1024
}

variable "dynamodb_enabled" {
  type    = bool
  default = false
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "places_provider" {
  type        = string
  description = "Production should use a real provider, not the fixture dataset."
  default     = "http"
}

variable "events_provider" {
  type    = string
  default = "http"
}
