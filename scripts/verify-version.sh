#!/usr/bin/env bash
set -euo pipefail

expected="${1#v}"
root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
file_version="$(tr -d '[:space:]' < "$root_dir/VERSION")"
frontend_version="$(cd "$root_dir/frontend" && npm pkg get version | tr -d '\"[:space:]')"
backend_version="$(cd "$root_dir/backend-java" && ./mvnw help:evaluate -Dexpression=project.version -q -DforceStdout)"

for actual in "$file_version" "$frontend_version" "$backend_version"; do
  if [[ "$actual" != "$expected" ]]; then
    echo "Version mismatch: tag=$expected actual=$actual" >&2
    exit 1
  fi
done

echo "Version $expected is consistent."
