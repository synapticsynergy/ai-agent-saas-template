variable "project" {
  description = "Project name, used as a resource name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name: dev, staging or prod."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zone_count" {
  description = "How many availability zones to span."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2
    error_message = "At least two availability zones are required for RDS."
  }
}

variable "enable_nat_gateway" {
  description = <<-EOT
    Whether to create a NAT gateway for private subnet egress.

    Only needed when a VPC-attached Lambda must reach the public internet. It is
    the most expensive resource in this module, so it is off by default and
    enabled per environment.
  EOT
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
