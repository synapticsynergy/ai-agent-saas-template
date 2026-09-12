variable "project" { type = string }
variable "environment" { type = string }

variable "api_base_url" {
  type        = string
  description = "Application API base URL. save_plan calls it with the caller's token."
}

variable "places_provider" {
  type        = string
  description = "fixture or http."
  default     = "fixture"
}

variable "events_provider" {
  type    = string
  default = "fixture"
}

variable "public_access" {
  type        = bool
  description = <<-EOT
    When false (the default) the Function URL requires SigV4, so only principals
    you grant lambda:InvokeFunctionUrl can reach it. Set true only if a hosted
    MCP client cannot sign requests, and understand that the tools then rely
    entirely on the API's own authorization.
  EOT
  default     = false
}

variable "image_uri" {
  type    = string
  default = ""
}

variable "image_retention_count" {
  type    = number
  default = 20
}

variable "memory_size" {
  type    = number
  default = 512
}

variable "timeout_seconds" {
  type    = number
  default = 60
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "extra_environment" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
