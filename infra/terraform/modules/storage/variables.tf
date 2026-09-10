variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "bucket_suffix" {
  type        = string
  description = <<-EOT
    Suffix making the bucket name globally unique. Bucket names are shared
    across all AWS accounts, so this must differ per deployment — the account id
    is a reasonable default.
  EOT
}

variable "versioning_enabled" {
  type    = bool
  default = true
}

variable "noncurrent_version_expiration_days" {
  type    = number
  default = 90
}

variable "dynamodb_enabled" {
  type        = bool
  description = "Create the optional DynamoDB table."
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
