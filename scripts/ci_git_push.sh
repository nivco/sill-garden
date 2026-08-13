#!/usr/bin/env bash
# Push bot commits without rebase conflicts on generated analytics JSON.
set -euo pipefail
git rebase --abort 2>/dev/null || true
git merge --abort 2>/dev/null || true
msg="${1:?commit message}"
shift
paths=("$@")

stage_changes() {
  git add "$@"
  if [ -z "${CI_SKIP_ANALYTICS_COMMIT:-}" ]; then
    git add -A -- products/analytics 2>/dev/null || true
  fi
  git add -A -- products/traffic 2>/dev/null || true
}

stage_changes "${paths[@]}"
if git diff --staged --quiet; then
  echo "No changes to commit."
  exit 0
fi

git fetch origin main

for attempt in 1 2 3 4 5; do
  git reset --mixed origin/main
  stage_changes "${paths[@]}"
  if git diff --staged --quiet; then
    echo "No changes after sync with origin/main."
    exit 0
  fi
  git commit -m "$msg"
  if git push origin main; then
    exit 0
  fi
  echo "Push attempt ${attempt} failed; retrying in $((attempt * 3))s..."
  git fetch origin main
  sleep $((attempt * 3))
done
echo "git push failed after 5 attempts" >&2
exit 1
