#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/tag_release.sh vX.Y.Z

Creates an annotated tag (vX.Y.Z) and pushes it to origin.

Examples:
  scripts/tag_release.sh v0.2.1
USAGE
}

TAG=${1:-}
if [[ -z "${TAG}" ]]; then
  usage
  exit 1
fi

# Accept vX.Y.Z and optional pre-release/build metadata
if ! [[ ${TAG} =~ ^v[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z\.-]+)?$ ]]; then
  echo "Error: tag must match vX.Y.Z (optionally with -prerelease/+build)." >&2
  exit 1
fi

# Ensure clean working tree
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Error: working tree not clean. Commit or stash changes first." >&2
  exit 1
fi

# Ensure tag does not already exist
if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
  echo "Error: tag ${TAG} already exists." >&2
  exit 1
fi

echo "Creating annotated tag ${TAG}..."
git tag -a "${TAG}" -m "Release ${TAG}"

echo "Pushing tag ${TAG} to origin..."
git push origin "${TAG}"

echo "Done. Now publish the GitHub Release for ${TAG}."

