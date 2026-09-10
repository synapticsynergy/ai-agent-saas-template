# Remote state for the prod environment.
#
# Each environment keeps its own state file. Sharing one would let a staging
# apply touch production resources, and would make a corrupted state file take
# down everything at once.
#
# Configure the bucket and lock table once per AWS account, then initialise:
#
#   terraform -chdir=infra/terraform/envs/prod init \
#     -backend-config=bucket=<your-tfstate-bucket> \
#     -backend-config=dynamodb_table=<your-lock-table>
#
# CI passes the same values from environment secrets. The partial configuration
# below is deliberate: the bucket name is account-specific and does not belong
# in the repository.

terraform {
  backend "s3" {
    key     = "prod/terraform.tfstate"
    region  = "us-west-2"
    encrypt = true
  }
}
