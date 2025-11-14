#!/bin/bash
# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
readonly PATHS_FILE="$SCRIPT_DIR/cli-docs-paths.txt"

cd "$REPO_ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "UNCHANGED" >&2
    echo "Not in a git repository" >&2
    exit 1
fi

if [[ ! -f "$PATHS_FILE" ]]; then
    echo "UNCHANGED" >&2
    echo "Paths file not found: $PATHS_FILE" >&2
    exit 1
fi

base_branch="origin/master"
if ! git rev-parse --verify "$base_branch" >/dev/null 2>&1; then
    base_branch="upstream/master"
    if ! git rev-parse --verify "$base_branch" >/dev/null 2>&1; then
        base_branch="HEAD~1"
    fi
fi

mapfile -t paths < <(grep -v '^\s*#' "$PATHS_FILE" | grep -v '^\s*$')

changed=false
for path in "${paths[@]}"; do
    if git diff --name-only "$base_branch...HEAD" -- "$path" 2>/dev/null | grep -q .; then
        changed=true
        break
    fi
    if git diff --name-only HEAD -- "$path" 2>/dev/null | grep -q .; then
        changed=true
        break
    fi
done

if [[ "$changed" == "true" ]]; then
    echo "CHANGED"
    exit 0
else
    echo "UNCHANGED"
    exit 1
fi

