# Postgres for the application.
#
# The instance lives in private subnets and is reachable only from the
# application security group — there is no public endpoint, in any environment.
# The master credential is generated here and stored in Secrets Manager; it is
# never a Terraform variable, so it cannot end up in a tfvars file or a shell
# history.

locals {
  name = "${var.project}-${var.environment}"
}

resource "random_password" "master" {
  length  = 32
  special = true
  # RDS rejects these in a master password.
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_db_instance" "this" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.database_name
  username = var.master_username
  password = random_password.master.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_days
  backup_window           = "07:00-08:00"
  maintenance_window      = "Mon:08:30-Mon:09:30"

  # Production must never be destroyed by an accidental `terraform destroy`,
  # and must leave a final snapshot behind if it ever is.
  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = !var.deletion_protection
  final_snapshot_identifier = var.deletion_protection ? "${local.name}-final-${formatdate("YYYYMMDDhhmmss", timestamp())}" : null

  auto_minor_version_upgrade = true
  apply_immediately          = var.environment != "prod"

  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = var.environment == "prod"

  tags = merge(var.tags, { Name = local.name })

  lifecycle {
    # The snapshot identifier embeds a timestamp, which would otherwise show up
    # as a diff on every plan.
    ignore_changes = [final_snapshot_identifier]
  }
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "/${var.project}/${var.environment}/database-url"
  description             = "Application connection string for ${local.name}"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id

  secret_string = jsonencode({
    # Async driver for the application, sync driver for Alembic migrations.
    DATABASE_URL      = "postgresql+asyncpg://${var.master_username}:${urlencode(random_password.master.result)}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${var.database_name}"
    DATABASE_SYNC_URL = "postgresql+psycopg://${var.master_username}:${urlencode(random_password.master.result)}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${var.database_name}"
  })
}
