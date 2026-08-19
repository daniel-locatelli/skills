---
name: preparing-pull-request
description: Use before opening ANY pull request or merge request (or filing an issue) on a repository you do not own, on GitHub or GitLab. Traces the defect's origin through blame, commit, PR and issue history, sweeps the upstream tracker for duplicate or in-flight work, and verifies every claim the PR body will make. Also invocable on a draft issue to verify it before filing.
---

# Preparing a pull request: origin trace + upstream sweep

Commands below are shown for GitHub (`gh`); the GitLab equivalents (`glab`)
follow each one. "PR" means merge request on GitLab.

Run ALL steps before committing or opening the PR, and fold every result into
a local draft (a notes file for the change) under a dated
`## Origin trace & upstream sweep (<date>)` section. No step is skippable: the
one you skip is the one that flips the story. Two real cases: a "leftover"
line turned out to be a merge-race reintroduction, which changed the PR from
"cleanup" to "regression fix"; an unswept tracker hid an in-flight refactor
that the PR would have collided with.

## 1. Re-verify against fresh main

- `git fetch origin main`; record the tip SHA and date.
- Confirm the defect/target lines still exist; refresh line numbers in the draft.

## 2. Origin trace (blame → commit → PR → issue)

- `git blame -L<start>,<end> <file>` on the target lines.
- If the blame commit is a refactor/move, dig deeper:
  `git log --all --reverse -S '<literal string>'` or `-G '<regex>'`.
- Map commits to PRs:
  `gh api "repos/<owner>/<repo>/commits/<sha>/pulls" --jq '.[] | "#\(.number) \(.title)"'`.
- Follow the PR to its originating issue, if any.
- Answer: who wrote it, in which PR, from which issue, and is the defect a
  **leftover**, a **reintroduction** (parallel branch / merge race), or
  **deliberate**? This decides the PR's framing.

## 3. Upstream sweep (duplicates + collisions)

- Search issues AND PRs, open AND closed, for the symbol and its synonyms:
  `gh search issues --repo <owner>/<repo> "<term>"` and
  `gh search prs --repo <owner>/<repo> "<term>"` (separate commands; run 2 to 4
  term variants: exact symbol, snake_case, human phrasing).
  GitLab: `glab issue list -R <owner>/<repo> --all --search "<term>"` and
  `glab mr list -R <owner>/<repo> --all --search "<term>"`.
- List open PRs touching the same files:
  `gh pr list --repo <owner>/<repo> --state open --json number,title,author,files --jq '.[] | select(.files[].path | test("<file>"))'`.
  GitLab: `glab mr list -R <owner>/<repo> -F json`, then
  `glab api "projects/<owner>%2F<repo>/merge_requests/<iid>/changes" | jq -r '.changes[].new_path'`
  for each candidate.
- Answer: is anyone already working on this, and which open PRs share the file
  (distinguish conflict risk from semantic overlap)?

## 4. Mechanism checks (test before stating)

- Run/verify every claim the PR body will make: imports resolve, no circular
  imports, the passthrough really is a passthrough, and so on.
- Grep the test suite for assertions that PIN the current (wrong) behavior:
  those tests must change in the same PR, and they change the PR's size class.
- A fix PR needs a regression test verified **red without the fix, green with it**.

## 5. Fold into the draft, then stop

- Write the findings into the draft's status line and trace section, including
  a one-sentence "good PR-body fact" distilled from the trace.
- **Do NOT commit or open the PR.** The user's explicit go is still required.
  When it comes, keep the PR body short: 3 to 5 sentences, one sentence of
  history, written in the user's own voice.
