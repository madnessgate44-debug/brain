#!/usr/bin/env bash
# Owner-run helper: put Shadow's Gemini pool into this repository's Actions secrets.
#
# The agent's token cannot write Actions secrets ("Resource not accessible by
# integration"), so a human runs this once. Values are read from your environment and
# piped straight into `gh secret set` (which encrypts them locally); nothing is printed.
#
# Usage:
#   export OHGeminiAPI=...  GEMINI_POOL_1=...  GEMINI_POOL_2=...  # etc.
#   ./scripts/install-pool-secrets.sh [owner/repo]
#
# Verify afterwards:
#   gh workflow run shadow-keys.yml --repo <owner/repo>
set -euo pipefail

REPO="${1:-madnessgate44-debug/brain}"
LABELS=(OHGeminiAPI GEMINI_POOL_1 GEMINI_POOL_2 GEMINI_POOL_3 GEMINI_POOL_4 GEMINI_POOL_5 GEMINI_POOL_6 GEMINI_POOL_7)

missing=0
for label in "${LABELS[@]}"; do
  value="${!label:-}"
  if [ -z "$value" ]; then
    echo "skip  ${label} (not set in your environment)"
    missing=$((missing + 1))
    continue
  fi
  printf '%s' "$value" | gh secret set "$label" --repo "$REPO"
  echo "set   ${label}"
done

if [ "$missing" -gt 0 ]; then
  echo "note: ${missing} label(s) were absent from your environment"
fi
echo "done. Verify with: gh workflow run shadow-keys.yml --repo ${REPO}"
