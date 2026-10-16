# coe - CLI Evaluation Framework

A lightweight CLI tool for testing and grading AI prompts using deterministic checks and model-based evaluation.

## Features

- **Easy Configuration**: Define evaluations in simple YAML files
- **Flexible Prompts**: Support inline prompts or file-based prompts
- **Two Runners**: Direct Anthropic API calls (`api`), or an agentic SDK loop with tool access (`agentic`)
- **Deterministic Checks**: Validate outputs, file contents, and git diffs with string matching rules
- **Model Evaluation**: Use Claude to grade outputs against custom rubrics
- **Results Tracking**: Track evaluation history with automatic dashboards
- **Activity Logs**: Agentic tool calls and text snippets are captured per run in the JSON output
- **Per-Repository Isolation**: Each repo maintains its own evaluation results
- **Runtime Evaluation**: Grade a skill's output in real time via Claude Code hooks, with automatic retry and human escalation

## Promotion vs Runtime Evaluation

`coe` supports two distinct testing strategies:

**Promotion Evaluation** (`coe promote`) is for refining and certifying prompts before production. It runs a prompt N times against fixed fixtures and measures pass rate. Use it to reach a confidence threshold (e.g., 95% pass rate) before promoting a prompt. Eval configs live in `evals/promotion/` and include detailed `setup` scripts, multiple runs, and targeted deterministic checks.

**Runtime Evaluation** (`coe runtime-check`) is for real-time quality gates in production workflows. It fires once after a Claude Code skill completes (via the `PostToolUse` hook), grades the actual output against the live repo state, and either lets the chain continue or sends feedback back to the agent for a retry. After 3 consecutive failures it escalates to a human. Runtime eval configs live in `evals/runtime/` and include `git_diff_contains` checks and a model rubric with a `pass_threshold`.

The two strategies are isolated: `coe promote` sets `COE_MODE=promotion` so the runtime hook skips during promotion runs.

## Installation

```bash
git clone <this-repo>
cd coe
pip install -e .
```

## Quick Start

### 1. Set Up Your Repository

In your repository root, create the eval directories and a `.coe.yml` config:

```bash
mkdir -p evals/promotion evals/runtime
```

```yaml
# .coe.yml at your repo root
eval_dir: evals/promotion
runtime_eval_dir: evals/runtime
```

See `example/.coe.yml` for a fully annotated example. `coe` also accepts a legacy `tests/coe/` directory if `.coe.yml` is absent.

### 2. Create a .env File (in coe repo)

Configure credentials in the coe repository. Required for `runner: claude-code`; optional if you only use `runner: api` with credentials already in your shell environment:

```bash
cd ~/Repos/coe
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 3. Create an Evaluation Config

Create `evals/promotion/my-prompt-eval.yml`:

```yaml
prompt-under-eval: |
  You are a helpful assistant. Answer the following question:

test_input:
  question: What is 2+2?

model_for_eval: claude-haiku-5-5
model_parameters:
  max_tokens: 1024

deterministic_checks:
  - name: Contains answer
    type: contains
    values:
      - "4"

model_evaluation:
  enabled: true
  model: claude-sonnet-5-5
  rubric: |
    Score 1-5 based on:
    - Correctness of answer
    - Clarity of explanation
```

### 4. Run Promotion Evaluations

From your repository root:

```bash
coe promote            # run all evals in evals/promotion/ (also: coe p)
coe promote my-prompt-eval.yml          # run a single eval
coe promote my-prompt-eval.yml -r 50   # run 50 times
coe promote --dir path/to/dir/         # override eval directory
```

`coe test` still works as a deprecated alias.

### 5. View the Dashboard

```bash
coe dashboard          # open the existing dashboard (also: coe dash, coe d)
coe dash build         # rebuild from existing result files, then open
coe dash --build       # same
coe dash -b            # same
```

Opens `evals/promotion/results/index.html` in your default browser. Use `build` when a run was interrupted before the dashboard regenerated.

### 6. Set Up Runtime Evaluation (optional)

Create `evals/runtime/<skill-name>.yml` (see `example/runtime-eval.yml`), then add a `PostToolUse` hook to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Skill",
      "hooks": [{
        "type": "command",
        "command": "bash -c '[ \"$COE_MODE\" = promotion ] && exit 0; coe runtime-check --from-hook'"
      }]
    }]
  }
}
```

The hook fires after each Claude Code skill completes. Test manually with:

```bash
coe runtime-check --skill my-skill-name
```

## Configuration

### prompt-under-eval

Can be either inline text or a file path:

```yaml
# Inline prompt
prompt-under-eval: |
  Your prompt text here...

# Or file reference (absolute path or relative to the .yml file)
prompt-under-eval: ~/.claude/skills/my-skill/SKILL.md
```

### model_for_eval

The Claude model to use for generation (e.g., `claude-haiku-5-5`, `claude-sonnet-5-5`). Always required. For the `claude-code` runner this is passed as `--model` to the Claude Code CLI.

### runner

Controls how the prompt is executed. Optional; defaults to `api`.

| Value | Behavior |
|---|---|
| `api` | Calls the Anthropic API directly. Fast; the model has no tool access. |
| `agentic` | Runs an SDK agentic loop. The model can call `read_file`, `write_file`, `list_directory`, and `run_command` tools across multiple turns. Use this for evals that require file manipulation or shell commands. |

```yaml
runner: agentic
```

### agent_options

Options for the `agentic` runner. Ignored when `runner: api`.

```yaml
agent_options:
  max_turns: 15               # limit agentic turns (default: 10)
  allowed_tools:              # restrict which tools are available (default: all four)
    - read_file
    - write_file
    - list_directory
    - run_command
```

#### Available tools

| Tool | Description |
|---|---|
| `read_file` | Read a file relative to the repo root |
| `write_file` | Write or create a file relative to the repo root |
| `list_directory` | List entries in a directory relative to the repo root |
| `run_command` | Run any shell command in the repo root and return stdout, stderr, and exit code (30 s timeout) |

Use `run_command` when the model needs to interact with CLI tools as part of the task. For example, to evaluate a prompt that reads and updates beads issues:

```yaml
runner: agentic
agent_options:
  allowed_tools:
    - run_command
  max_turns: 5

prompt-under-eval: |
  List all open beads issues with `bd list --status=open`, then summarize them.
  Your response must include each issue ID and title.

deterministic_checks:
  - name: Contains a beads ID
    type: contains
    values:
      - "beads-"
```

### model_parameters

Parameters for the `api` runner. Optional; defaults to `max_tokens: 1024`. Ignored when `runner: claude-code`.

```yaml
model_parameters:
  max_tokens: 4096
```

### test_input

Dictionary of inputs appended to the prompt after a separator. Optional.

```yaml
test_input:
  user_question: What is AI?
  context: General knowledge
```

### deterministic_checks

Array of string matching checks. Four types are supported:

- `contains` / `does_not_contain` — match against the model's text response
- `file_contains` / `file_does_not_contain` — match against a file on disk; `file` is relative to the repo root
- `git_diff_contains` / `git_diff_does_not_contain` — match against `git diff HEAD` output; useful in runtime eval configs to verify a skill modified the expected files

```yaml
deterministic_checks:
  - name: Must contain conclusion
    type: contains
    values:
      - "therefore"
      - "in conclusion"

  - name: No profanity
    type: does_not_contain
    values:
      - "badword1"
      - "badword2"

  - name: Output file has expected line
    type: file_contains
    file: path/to/output.md    # relative to repo root
    values:
      - "[x] Task is complete"

  - name: Output file has no unchecked marker
    type: file_does_not_contain
    file: path/to/output.md
    values:
      - "[ ] Task is complete"
```

### setup

Optional shell scripts to run before and/or after each model call. Paths are relative to the repo root. Use `before` to reset state and `after` to clean up.

```yaml
setup:
  before: tests/coe/reset_eval.sh
  after: tests/coe/reset_eval.sh
```

### model_evaluation

Optional Claude-based grading via a direct API call. Always uses the Anthropic API regardless of `runner`.

```yaml
model_evaluation:
  enabled: true
  model: claude-sonnet-5-5  # Optional; defaults to model_for_eval
  pass_threshold: 4         # Score must be >= this to pass (default: 4, range 1-5)
  rubric: |
    Grade 1-5 based on:
    - Relevance to prompt
    - Quality of reasoning
```

`pass_threshold` is particularly useful in runtime eval configs where you want a stricter or looser bar than the promotion default.

## Results

Results are saved to `evals/promotion/results/` (or wherever `eval_dir` points in `.coe.yml`):

- `[timestamp].json` - Individual run results
- `index.html` - Interactive dashboard showing all results
- `static/` - Supporting assets for the dashboard

Open `evals/promotion/results/index.html` in your browser to view the evaluation timeline.

### Result JSON structure

Each run produces a timestamped JSON file:

```json
{
  "prompt_name": "my-prompt-eval",
  "test_input": { "question": "What is 2+2?" },
  "output": "The answer is 4.",
  "deterministic_checks": { ... },
  "model_evaluation": { "enabled": true, "score": 5, "reasoning": "...", "pass": true },
  "passed": true,
  "duration_seconds": 1.23,
  "timestamp": "2026-10-13T15:30:45.123456",
  "logs": ["→ run_command: bd list --status=open", "→ list_directory: src/", "✎ Here is what I found..."]
}
```

`logs` contains the activity from agentic runs (tool calls and text snippets). It is always present but empty for `runner: api`.

### Dashboard

The dashboard pass rate displayed on prompt cards, per-prompt stats, and the overview header is calculated over the **20 most recent runs** for each prompt, not the full history. All-time run counts are still shown for context.

## Long Runs

On macOS, the system may sleep during a long batch run, interrupting it. Wrap the command with `caffeinate` to prevent idle sleep for the duration:

```bash
caffeinate -i coe promote my-eval.yml -r 50
```

To keep a run alive across terminal disconnects or closing the lid, use tmux:

```bash
tmux new -s evals
caffeinate -i coe promote my-eval.yml -r 50
# detach without stopping: Ctrl-B D
# reattach later:          tmux attach -t evals
```

## Examples

See `example/sample-eval.yml` for a complete promotion eval example. See `example/runtime-eval.yml` for a runtime eval config with annotations.

## License

MIT
