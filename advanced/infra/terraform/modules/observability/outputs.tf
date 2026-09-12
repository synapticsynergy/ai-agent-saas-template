output "alert_topic_arn" {
  description = "SNS topic alarms publish to, when created here."
  value       = var.create_alert_topic ? aws_sns_topic.alerts[0].arn : ""
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.this.dashboard_name
}
