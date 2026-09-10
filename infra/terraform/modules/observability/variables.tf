variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }

variable "api_function_name" {
  type = string
}

variable "api_log_group_name" {
  type        = string
  description = "Log group the permission-denied metric filter reads."
}

variable "create_alert_topic" {
  type        = bool
  description = "Create an SNS topic for alarms. Set false to reuse an existing one via alarm_action_arns."
  default     = true
}

variable "alarm_action_arns" {
  type        = list(string)
  description = "Existing alarm targets, used when create_alert_topic is false."
  default     = []
}

variable "error_threshold" {
  type    = number
  default = 5
}

variable "latency_threshold_ms" {
  type    = number
  default = 3000
}

variable "permission_denied_threshold" {
  type        = number
  description = "Denials per five minutes before alarming. Some denials are normal."
  default     = 25
}

variable "tags" {
  type    = map(string)
  default = {}
}
