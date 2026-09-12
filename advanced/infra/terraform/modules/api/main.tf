# The FastAPI application, deployed as a Lambda container image behind an
# HTTP API Gateway.
#
# Terraform owns the function, its role, the ECR repository and the gateway.
# It does *not* own the image tag: `make api-deploy` publishes a new image and
# points the function at it, so a deploy is not an infrastructure change. That
# keeps `terraform plan` free of churn from ordinary application releases, and
# makes rollback "point at the previous tag".

locals {
  name = "${var.project}-${var.environment}-api"
}

data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# Image registry
# ---------------------------------------------------------------------------

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
      description  = "Keep the most recent images; older ones are unreachable rollback targets anyway."
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.image_retention_count
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# Execution role
# ---------------------------------------------------------------------------

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

resource "aws_iam_role_policy_attachment" "vpc_access" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Scoped by hand rather than using the managed policies: the application needs
# exactly these actions on exactly these resources, and a managed policy would
# grant more.
data "aws_iam_policy_document" "runtime" {
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }

  statement {
    sid       = "ReadDatabaseSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.database_secret_arn]
  }

  statement {
    sid    = "TenantObjectStorage"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    # Only under the tenant prefix the application actually writes.
    resources = ["${var.storage_bucket_arn}/organizations/*"]
  }

  statement {
    sid       = "ListOwnBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [var.storage_bucket_arn]
  }

  dynamic "statement" {
    for_each = var.dynamodb_table_arn == "" ? [] : [1]
    content {
      sid    = "DynamoDb"
      effect = "Allow"
      actions = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
      ]
      resources = [var.dynamodb_table_arn, "${var.dynamodb_table_arn}/index/*"]
    }
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "${local.name}-runtime"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.runtime.json
}

# ---------------------------------------------------------------------------
# Function
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "this" {
  function_name = local.name
  role          = aws_iam_role.this.arn
  package_type  = "Image"

  # Placeholder on first apply; `make api-deploy` replaces it with a real image.
  # Terraform ignores the value afterwards so releases are not plan churn.
  image_uri = var.image_uri != "" ? var.image_uri : "${aws_ecr_repository.this.repository_url}:bootstrap"

  memory_size = var.memory_size
  timeout     = var.timeout_seconds

  environment {
    variables = merge(
      {
        APP_ENV              = var.environment
        LOG_LEVEL            = var.log_level
        WORKOS_CLIENT_ID     = var.workos_client_id
        S3_BUCKET            = var.storage_bucket_name
        DYNAMODB_ENABLED     = var.dynamodb_table_arn == "" ? "0" : "1"
        DYNAMODB_TABLE       = var.dynamodb_table_name
        API_CORS_ORIGINS     = var.cors_origins
        DATABASE_SECRET_NAME = var.database_secret_name
        # AWS_ENDPOINT_URL is intentionally unset: it points the SDK at
        # LocalStack, and app.config refuses to start with it outside local.
      },
      var.extra_environment,
    )
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [var.security_group_id]
  }

  tracing_config {
    mode = "Active"
  }

  depends_on = [
    aws_iam_role_policy.runtime,
    aws_cloudwatch_log_group.this,
  ]

  tags = var.tags

  lifecycle {
    # The deploy pipeline owns the image; Terraform owns everything else.
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.this.function_name
  function_version = "$LATEST"

  lifecycle {
    ignore_changes = [function_version]
  }
}

# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "this" {
  name          = local.name
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins     = split(",", var.cors_origins)
    allow_methods     = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    allow_headers     = ["authorization", "content-type", "x-request-id", "x-run-id", "x-trace-id"]
    allow_credentials = true
    max_age           = 300
  }

  tags = var.tags
}

resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = var.timeout_seconds * 1000
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.this.id}"
}

resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.this.id}"
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    # No headers or query strings: they carry bearer tokens.
    format = jsonencode({
      requestId        = "$context.requestId"
      httpMethod       = "$context.httpMethod"
      path             = "$context.path"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      responseLatency  = "$context.responseLatency"
      integrationError = "$context.integrationErrorMessage"
    })
  }

  default_route_settings {
    throttling_burst_limit = var.throttling_burst_limit
    throttling_rate_limit  = var.throttling_rate_limit
  }

  tags = var.tags
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
