#!/bin/sh
# Fail if the built frontend bundle contains anything that looks like a secret.
set -eu
DIST="${1:-frontend/dist}"
if [ ! -d "$DIST" ]; then
  echo "No build output at $DIST; run the frontend build first." >&2
  exit 1
fi
PATTERN='sk-(proj-|svcacct-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}|tvly-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9]{20,}|(OPENAI|GEMINI|TAVILY|GROQ)_API_KEY'
if grep -rEl "$PATTERN" "$DIST"; then
  echo "Possible secret found in the frontend bundle (files listed above)." >&2
  exit 1
fi
echo "Bundle check passed: no secrets in $DIST"
