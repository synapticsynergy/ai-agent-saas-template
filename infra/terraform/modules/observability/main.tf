# Alarms and dashboards.
#
# Deliberately small: a handful of alarms someone will actually act on beats a
# wall of metrics nobody reads. Authorization failures get their own alarm
# because a spike in them is a signal worth waking up for, not noise.

locals {
  name = "${var.project}-${var.environment}"
}

resource "aws_sns_topic" "alerts" {
  count = var.create_alert_topic ? 1 : 0

  name = "${local.name}-alerts"
  tags = var.tags
}

locals {
  alarm_targets = var.create_alert_topic ? [aws_sns_topic.alerts[0].arn] : var.alarm_action_arns
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${local.name}-api-5xx"
  alarm_description   = "The API is returning server errors."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = var.error_threshold
  treat_missing_data  = "notBreaching"

  metric_name = "Errors"
  namespace   = "AWS/Lambda"
  period      = 300
  statistic   = "Sum"

  dimensions = { FunctionName = var.api_function_name }

  alarm_actions = local.alarm_targets
  ok_actions    = local.alarm_targets
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${local.name}-api-latency"
  alarm_description   = "API p99 latency is above the target."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.latency_threshold_ms
  treat_missing_data  = "notBreaching"

  metric_name        = "Duration"
  namespace          = "AWS/Lambda"
  period             = 300
  extended_statistic = "p99"

  dimensions = { FunctionName = var.api_function_name }

  alarm_actions = local.alarm_targets
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "api_throttles" {
  alarm_name          = "${local.name}-api-throttles"
  alarm_description   = "The API is being throttled by concurrency limits."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  treat_missing_data  = "notBreaching"

  metric_name = "Throttles"
  namespace   = "AWS/Lambda"
  period      = 300
  statistic   = "Sum"

  dimensions = { FunctionName = var.api_function_name }

  alarm_actions = local.alarm_targets
  tags          = var.tags
}

# Structured logs make authorization denials countable. A sustained spike means
# either a broken permission mapping or someone probing.
resource "aws_cloudwatch_log_metric_filter" "permission_denied" {
  name           = "${local.name}-permission-denied"
  log_group_name = var.api_log_group_name
  pattern        = "{ $.code = \"permission_denied\" }"

  metric_transformation {
    name          = "PermissionDenied"
    namespace     = "${var.project}/${var.environment}"
    value         = "1"
    default_value = 0
  }
}

resource "aws_cloudwatch_metric_alarm" "permission_denied" {
  alarm_name          = "${local.name}-permission-denied-spike"
  alarm_description   = "Unusual volume of authorization failures."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = var.permission_denied_threshold
  treat_missing_data  = "notBreaching"

  metric_name = aws_cloudwatch_log_metric_filter.permission_denied.metric_transformation[0].name
  namespace   = "${var.project}/${var.environment}"
  period      = 300
  statistic   = "Sum"

  alarm_actions = local.alarm_targets
  tags          = var.tags
}

resource "aws_cloudwatch_dashboard" "this" {
  dashboard_name = local.name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "API invocations and errors"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.api_function_name],
            [".", "Errors", ".", "."],
            [".", "Throttles", ".", "."],
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "API latency"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.api_function_name, { stat = "p50" }],
            ["...", { stat = "p99" }],
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title   = "Authorization failures"
          region  = var.region
          metrics = [["${var.project}/${var.environment}", "PermissionDenied"]]
          period  = 300
          stat    = "Sum"
        }
      },
    ]
  })
}
