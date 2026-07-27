#!/usr/bin/env bash
set -euo pipefail

release_root="${1:?usage: check-release-contents.sh <directory>}"
release_root="$(cd "$release_root" && pwd)"

forbidden='(^|/)(\.env($|/)|env\.deploy$|logs($|/)|storage($|/)|models($|/)|node_modules($|/)|target($|/)|dist($|/)|coverage($|/)|test-results($|/)|\.git($|/))|\.(pem|key|p12|pfx|jks|db|sqlite|log)$'

violations="$(find "$release_root" -type f -print \
  | sed "s#^$release_root/##" \
  | grep -E "$forbidden" || true)"
if [[ -n "$violations" ]]; then
  echo "Forbidden release contents:" >&2
  echo "$violations" >&2
  exit 1
fi

large_files="$(find "$release_root" -type f -size +100M -print || true)"
if [[ -n "$large_files" ]]; then
  echo "Files larger than 100 MB are not allowed:" >&2
  echo "$large_files" >&2
  exit 1
fi

echo "Release content check passed."
