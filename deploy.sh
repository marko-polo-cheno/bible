#!/usr/bin/env bash
#
# One-shot deploy: build the frontend, publish it to GitHub Pages,
# then commit + push the built files (index.html etc.) to main.
#
# Usage:
#   ./deploy.sh                 # commit message defaults to "auto push"
#   ./deploy.sh "my message"    # custom commit message
#
set -euo pipefail

# Always run from the repo root (the folder this script lives in),
# no matter where you call it from.
cd "$(dirname "$0")"

COMMIT_MSG="${1:-auto push}"

echo "==> [1/4] Building frontend (yarn build)..."
cd frontend
if [ ! -d node_modules ]; then
  echo "    node_modules missing, running yarn install first..."
  yarn install
fi
yarn build

echo "==> [2/4] Publishing to GitHub Pages (yarn deploy -> gh-pages branch)..."
yarn deploy

cd ..

echo "==> [3/4] Staging + committing built files to main..."
git add -A
if git diff --cached --quiet; then
  echo "    Nothing new to commit."
else
  git commit -m "$COMMIT_MSG"
fi

echo "==> [4/4] Pushing to origin/main..."
git push

echo "==> Done. Live site updates on gh-pages; source + dist pushed to main."
