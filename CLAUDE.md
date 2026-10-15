# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Conservative (default)**: Use `bd` for task tracking. Do not run git commits, git pushes, or Dolt remote sync unless explicitly asked. At handoff, report changed files, validation, and suggested next commands.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; use the same conservative git policy unless active instructions say otherwise.
- **Team-maintainer**: Only when the repository explicitly opts in, agents may close beads, run quality gates, commit, and push as part of session close. A current "do not commit" or "do not push" instruction still wins.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Handle git/sync by active profile**:
   ```bash
   # Conservative/minimal/default: report status and proposed commands; wait for approval.
   git status

   # Team-maintainer opt-in only, unless current instructions forbid it:
   git pull --rebase
   git push
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- Do not commit or push without clear authority from the active profile or the current user request.
- If a required sync or push is blocked, stop and report the exact command and error.
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
pip install -e .          # install in editable mode
coe test                  # run all evals in tests/coe/
coe test my-eval.yml      # run a single eval
coe test my-eval.yml -r 5 # run 5 times (default: 20)
coe dash                  # open the results dashboard
coe dash build            # rebuild dashboard from existing results, then open
```

No test framework is configured. The `coe test` command is the primary way to exercise the evaluator logic.

## Architecture Overview

`coe` is a Python CLI evaluation framework for testing and grading AI prompts against a repo. It runs prompts (inline or from files) through the Anthropic API and scores them with deterministic checks and optional model-graded rubrics.

**Package layout:**

```
coe/
  cli.py                      # entry point; argparse commands; agentic tool loop
  config/
    yaml_loader.py             # loads and validates eval YAML files
  evaluators/
    deterministic.py           # runs contains/file_contains/does_not_contain checks
    model_grader.py            # runs model-graded rubric scoring
  storage/
    results_writer.py          # writes timestamped JSON to tests/coe/results/
    history_reader.py          # reads all results for dashboard aggregation
    changelog_manager.py       # manages tests/coe/results/changelog.json
  dashboard/
    generator.py               # renders Jinja2 template → tests/coe/results/index.html
    templates/prompt_timeline.html
    static/dashboard.js
```

**Eval discovery:** `coe` walks up from CWD to find `tests/coe/`, then globs `*.yml`. Results land in `tests/coe/results/`.

**Agentic runner:** when `runner: agentic` is set, the eval runs an SDK tool loop giving the model `read_file`, `write_file`, `list_directory`, and `run_command`. The loop uses `_repo_root` (the nearest `.git` ancestor of the eval file) as CWD for all tool calls.

## Environment Variables

Stored in `.env` at the repo root (loaded by `coe test` via python-dotenv):

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | one of these two | Anthropic API key |
| `ANTHROPIC_AUTH_TOKEN` | one of these two | Alternative auth token |
| `ANTHROPIC_BASE_URL` | no | Custom API endpoint (e.g. Azure Gov) |

## Conventions & Patterns

**Eval file format** (`tests/coe/*.yml`):

```yaml
prompt-under-eval: "inline text" or "path/to/file.md"  # required; ~ is expanded
model_for_eval: claude-haiku-4-5-20251001               # required
deterministic_checks:                                   # required
  - name: "check name"
    type: contains | does_not_contain | file_contains | file_does_not_contain
    values: ["string to match"]
    file: relative/path.md   # required for file_contains / file_does_not_contain

runner: agentic               # optional; default: api
agent_options:
  max_turns: 15
  allowed_tools: [read_file, write_file, list_directory, run_command]
model_parameters:
  max_tokens: 8096
model_evaluation:
  enabled: true
  model: claude-sonnet-5-5
  rubric: |
    ...scoring rubric...
setup:
  before: reset_eval.sh       # runs before each eval run
  after: reset_eval.sh        # runs after each result is written
```

**Result files:** each run writes `tests/coe/results/<ISO-timestamp>.json` containing output, deterministic check results, model eval score, pass/fail, duration, and turn count.
