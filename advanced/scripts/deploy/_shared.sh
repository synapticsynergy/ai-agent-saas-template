# Sourced by the per-service deploy scripts. Not executable on its own.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: '$1' is required for this deploy but is not installed." >&2
    [ -n "${2:-}" ] && echo "       $2" >&2
    exit 1
  }
}

tf_output() {
  terraform -chdir="infra/terraform/envs/${ENV_NAME}" output -raw "$1" 2>/dev/null || true
}

# Immutable image tag. Deploys are traceable back to a commit, and rollback is
# "point the function at the previous tag" rather than "rebuild and hope".
image_tag() {
  echo "${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
}

ecr_login() {
  local registry="$1"
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$registry" >/dev/null
}

build_push_lambda_image() {
  local service="$1" dockerfile="$2" repo_url="$3" tag="$4"
  local registry="${repo_url%%/*}"

  ecr_login "$registry"
  echo "==> building $service image ($tag)"
  docker build --platform linux/amd64 -f "$dockerfile" --target lambda -t "$repo_url:$tag" .
  docker push "$repo_url:$tag"
}
