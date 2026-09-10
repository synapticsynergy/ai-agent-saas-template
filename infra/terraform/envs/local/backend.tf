# Local state, kept on disk. Nothing here is durable or shared: `make
# infra-reset` throws the whole environment away.
terraform {
  backend "local" {}
}
