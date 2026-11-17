#!/usr/bin/env bash
# Checks that manifest.json carries a valid version and that the integration
# changelog has a matching "## <version> ..." section. Prints the version.
set -euo pipefail
manifest=custom_components/advanced_google_contacts/manifest.json
changelog=custom_components/advanced_google_contacts/README.md

version=$(jq -r '.version // empty' "$manifest")
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "::error file=$manifest::version must look like X.Y.Z, got '${version}'" >&2
  exit 1
fi
if ! grep -qE "^## ${version//./\\.}( |$)" "$changelog"; then
  echo "::error file=$changelog::changelog section '## ${version} ...' is missing" >&2
  exit 1
fi
echo "$version"
