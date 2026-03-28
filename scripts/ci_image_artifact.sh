#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CI_IMAGE_TAG_SUFFIX="${CI_IMAGE_TAG_SUFFIX:-local}"
CI_DEV_IMAGE_REPO="${CI_DEV_IMAGE_REPO:-auraxis-ci-dev}"
CI_PROD_IMAGE_REPO="${CI_PROD_IMAGE_REPO:-auraxis-ci-prod}"
CI_DEV_DOCKERFILE="${CI_DEV_DOCKERFILE:-Dockerfile}"
CI_PROD_DOCKERFILE="${CI_PROD_DOCKERFILE:-Dockerfile.prod}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/ci_image_artifact.sh build <dev|prod> [image-ref]
  bash scripts/ci_image_artifact.sh save <image-ref> <archive-path>
  bash scripts/ci_image_artifact.sh load <archive-path>
  bash scripts/ci_image_artifact.sh ref <dev|prod>
EOF
}

image_ref_for_profile() {
  local profile="$1"
  case "$profile" in
    dev)
      echo "${CI_DEV_IMAGE_REPO}:${CI_IMAGE_TAG_SUFFIX}"
      ;;
    prod)
      echo "${CI_PROD_IMAGE_REPO}:${CI_IMAGE_TAG_SUFFIX}"
      ;;
    *)
      echo "Unsupported profile: ${profile}" >&2
      return 1
      ;;
  esac
}

dockerfile_for_profile() {
  local profile="$1"
  case "$profile" in
    dev)
      echo "$CI_DEV_DOCKERFILE"
      ;;
    prod)
      echo "$CI_PROD_DOCKERFILE"
      ;;
    *)
      echo "Unsupported profile: ${profile}" >&2
      return 1
      ;;
  esac
}

build_image() {
  local profile="$1"
  local image_ref="${2:-$(image_ref_for_profile "$profile")}"
  docker build -f "$(dockerfile_for_profile "$profile")" -t "$image_ref" .
}

save_image() {
  local image_ref="$1"
  local archive_path="$2"
  mkdir -p "$(dirname "$archive_path")"
  docker save "$image_ref" | gzip -c > "$archive_path"
}

load_image() {
  local archive_path="$1"
  gzip -dc "$archive_path" | docker load
}

main() {
  local command="${1:-}"
  case "$command" in
    build)
      [[ $# -ge 2 ]] || {
        usage
        return 2
      }
      build_image "$2" "${3:-}"
      ;;
    save)
      [[ $# -eq 3 ]] || {
        usage
        return 2
      }
      save_image "$2" "$3"
      ;;
    load)
      [[ $# -eq 2 ]] || {
        usage
        return 2
      }
      load_image "$2"
      ;;
    ref)
      [[ $# -eq 2 ]] || {
        usage
        return 2
      }
      image_ref_for_profile "$2"
      ;;
    *)
      usage
      return 2
      ;;
  esac
}

main "$@"
