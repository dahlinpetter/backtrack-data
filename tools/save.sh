#!/usr/bin/env bash
# Save collected data: commit and push. If another job saved the same files in the meantime, a rebase conflict in a
# shared data file (e.g. the monthly observations) can't be retried away, so start again from the latest saved data,
# collect once more on top of it and save that. Fails loudly only if all four tries fail.
# usage: tools/save.sh "<commit prefix>" "<paths to add>" "<command that collects again>"
set -e
msg=$1; paths=$2; regen=$3
git config user.name "delay-bot"; git config user.email "delay-bot@users.noreply.github.com"
for i in 1 2 3 4; do
  git add $paths
  if git diff --cached --quiet; then echo "Nothing new to save."; exit 0; fi
  git commit -qm "$msg: $(date -u +%FT%TZ) [skip ci]"
  if git pull --rebase -q origin main && git push -q origin HEAD:main; then echo "Saved (try $i)."; exit 0; fi
  git rebase --abort 2>/dev/null || true
  echo "::warning::Try $i clashed with another job's save. Collecting again on top of the latest data."
  git fetch -q origin main && git reset -q --hard origin/main
  sleep $((i * 4))
  bash -c "$regen"
done
echo "::error::Could not save after 4 tries."; exit 1
