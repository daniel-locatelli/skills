#!/usr/bin/env bash
# Run the six eval prompts x 3 runs with `claude -p`, each in a fresh empty
# directory outside the repo, so the answer cannot find scripts/cite.py.
#   run.sh <arm> [workdir]     arm = baseline | gate
# Answers go to runs/<arm>/<id>-<run>.md; files a run writes stay in workdir.
set -u
ARM=$1
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE/runs/$ARM
WORK=${2:-$(mktemp -d)}/$ARM
mkdir -p "$OUT" "$WORK"
one() {
  id=$1; run=$2
  prompt=$(python -c "import json,sys;print(next(p['prompt'] for p in json.load(open(sys.argv[1],encoding='utf-8')) if p['id']==int(sys.argv[2])))" "$HERE/prompts.json" "$id")
  d="$WORK/$id-$run"; rm -rf "$d"; mkdir -p "$d"
  # skip-permissions is acceptable: each run is in a throwaway empty directory outside the repo
  (cd "$d" && claude -p "$prompt" --model claude-opus-5-5 --dangerously-skip-permissions --output-format text > "$OUT/$id-$run.md" 2> "$d.err"); rc=$?
  # append files the run wrote (not __pycache__) to the answer, as for the baseline prompt-5 runs
  find "$d" -type f -not -path '*/__pycache__/*' | sort | while read -r f; do
    name=${f#"$d"/}; lang=""; case "$f" in *.py) lang=python;; esac
    { printf '\n\n---\n\n## File written by the run: `%s`\n\n```%s\n' "$name" "$lang"; cat "$f"; printf '\n```\n'; } >> "$OUT/$id-$run.md"
  done
  echo "$id-$run exit $rc bytes $(wc -c < "$OUT/$id-$run.md")"
}
for run in 1 2 3; do
  for id in 1 2 3 4 5 6; do one "$id" "$run" & done
  wait
done
echo "workdir: $WORK"
