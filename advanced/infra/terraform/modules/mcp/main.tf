# The MCP server, deployed as a Lambda container image behind a Function URL.
#
# A Function URL rather than API Gateway because the only client is the agent
# (or an AgentCore Gateway target), not a browser: there is no CORS story to
# manage and no per-route configuration to express.
#
# The MCP server holds no credential of its own. It forwards the caller's
# bearer assertion to the application API, which decides. That is why its IAM
# role grants almost nothing.

locals {
  name = "${var.project}-${var.environment}-mcp"
}

resource "aws_ecr_repository" "this" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.environment != "prod"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the most recent images."
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.image_retention_count
      }
      action = { type = "expire" }
    }]
  })
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = local.name
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

data "aws_iam_policy_document" "runtime" {
  statement {
    sid       = "Logs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "${local.name}-runtime"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.runtime.json
}

resource "aws_lambda_function" "this" {
  function_name = local.name
  role          = aws_iam_role.this.arn
  package_type  = "Image"
  image_uri     = var.image_uri != "" ? var.image_uri : "${aws_ecr_repository.this.repository_url}:bootstrap"

  memory_size = var.memory_size
  timeout     = var.timeout_seconds

  environment {
    variables = merge(
      {
        APP_ENV         = var.environment
        LOG_LEVEL       = var.log_level
        API_BASE_URL    = var.api_base_url
        PLACES_PROVIDER = var.places_provider
        EVENTS_PROVIDER = var.events_provider
      },
      var.extra_environment,
    )
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [aws_iam_role_policy.runtime, aws_cloudwatch_log_group.this]
  tags       = var.tags

  lifecycle {
    ignore_changes = [image_uri]
  }
}

# AWS_IAM auth: the caller must sign requests with SigV4. The MCP server is not
# a public endpoint, and the agent's execution role is the only principal that
# needs to reach it.
resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = var.public_access ? "NONE" : "AWS_IAM"
  invoke_mode        = "RESPONSE_STREAM"
}
