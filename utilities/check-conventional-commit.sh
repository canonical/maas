#!/usr/bin/env bash
set -euo pipefail

# check-conventional-commit.sh
#
# Validate a commit message against the MAAS MA201 - Conventional commits spec.
#
# Usage:
#   ./check-conventional-commit.sh "<commit message>"

ALLOWED_TYPES_RE='feat|fix|refactor|perf|test|chore|docs'
ALLOWED_SCOPES_RE='bootresources|dhcp|dns|network|power|proxy|security|storage|tftp|deps|ci'

die() {
  echo "ERROR: $*" >&2
  exit 1
}

usage() {
  cat >&2 <<'EOF'
Usage:
  check-conventional-commit.sh "<commit message>"
EOF
  exit 1
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
fi

if [[ $# -ne 1 ]]; then
  usage
fi

MSG="$1"

if [[ -z "$MSG" ]]; then
  die "Empty commit message"
fi

subject="$(echo "$MSG" | head -n 1)"

# Validate header syntax:
#    <type>[(<scope>)][!]: <description>
header_re="^(${ALLOWED_TYPES_RE})(\((${ALLOWED_SCOPES_RE})\))?(!)?:[[:space:]]+.+$"
if ! [[ "$subject" =~ $header_re ]]; then
  die "Commit subject does not match required format: <type>[(<scope>)][!]: <description>
Allowed types  : ${ALLOWED_TYPES_RE//|/, }
Allowed scopes : ${ALLOWED_SCOPES_RE//|/, }
Got: $subject"
fi

type="${BASH_REMATCH[1]}"
scope="${BASH_REMATCH[3]:-}"
bang="${BASH_REMATCH[4]:-}"

# The 'ci' scope is only allowed with the 'chore' type.
if [[ "$scope" == "ci" && "$type" != "chore" ]]; then
  die "Scope 'ci' can only be used with type 'chore'. Got: ${type}(ci)"
fi

# If '!' present, require "BREAKING CHANGE: <description>" footer
if [[ -n "$bang" ]]; then
  if ! printf '%s\n' "$MSG" | grep -Eq '^BREAKING CHANGE:[[:space:]]+.+$'; then
    die "Header contains '!' (breaking change) but no 'BREAKING CHANGE: <description>' footer was found."
  fi
fi

# fix commits must include a bug reference (case-insensitive).
# Accepted keywords: close, closes, closed, fix, fixes, fixed, resolve, resolves, resolved
# An optional colon may follow the keyword.
# Example valid footers:
#   Resolves LP: #1234567
#   fixes: LP: #1234567
#   Closed LP: #1234567
BUG_REF_KEYWORDS="close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved"
BUG_REF_RE="^(${BUG_REF_KEYWORDS}):?[[:space:]]+LP:[[:space:]]?[0-9]+$"

if [[ "$type" == "fix" ]]; then
  if ! printf '%s\n' "$MSG" | grep -Eiq "$BUG_REF_RE"; then
    die "Type is 'fix' but no bug reference footer was found. Add the reference to the Launchpad bug:
  Resolves LP:<bug-number>"
  fi
fi

echo "OK: Conventional Commit compliant."

