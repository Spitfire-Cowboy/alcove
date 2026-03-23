#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

chmod +x .githooks/commit-msg
git config core.hooksPath .githooks

echo "Installed repo git hooks (core.hooksPath=.githooks)."
