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
  (cd "$d" && claude -p "$prompt" --model claude-opus-5-5 --dangerously-skip-permissions --output-format text > "$OUT/$id-$run.md" 2> "$d.err")
  echo "$id-$run exit $? bytes $(wc -c < "$OUT/$id-$run.md")"
}
for run in 1 2 3; do
  for id in 1 2 3 4 5 6; do one "$id" "$run" & done
  wait
done
echo "workdir: $WORK"
