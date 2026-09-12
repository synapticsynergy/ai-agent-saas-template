variable "project" {
  type        = string
  description = "Project name, used as a resource name prefix."
}

variable "environment" {
  type        = string
  description = "Environment name: dev, staging or prod."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet ids for the DB subnet group."
}

variable "security_group_id" {
  type        = string
  description = "Security group allowing Postgres from the application only."
}

variable "database_name" {
  type        = string
  description = "Initial database name."
  default     = "app"
}

variable "master_username" {
  type        = string
  description = "Master username. The password is generated, never supplied."
  default     = "app"
}

variable "engine_version" {
  type        = string
  description = "Postgres major version."
  default     = "17"
}

variable "instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  type        = number
  description = "Initial storage in GiB."
  default     = 20
}

variable "max_allocated_storage" {
  type        = number
  description = "Autoscaling ceiling in GiB."
  default     = 100
}

variable "multi_az" {
  type        = bool
  description = "Whether to run a standby in a second availability zone."
  default     = false
}

variable "backup_retention_days" {
  type        = number
  description = "Automated backup retention."
  default     = 7
}

variable "deletion_protection" {
  type        = bool
  description = "Blocks deletion and forces a final snapshot. Always true in production."
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
