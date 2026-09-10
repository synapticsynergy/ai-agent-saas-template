variable "project" {
  type    = string
  default = "ai-agent-saas"
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

variable "dynamodb_enabled" {
  type    = bool
  default = true
}
