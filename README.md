# coe - CLI Evaluation Framework

A lightweight CLI tool for testing and grading AI prompts using deterministic checks and model-based evaluation.

## Features

- **Easy Configuration**: Define evaluations in simple YAML files
- **Flexible Prompts**: Support inline prompts or file-based prompts
- **Two Runners**: Direct Anthropic API calls (`api`), or an agentic SDK loop with tool access (`agentic`)
- **Deterministic Checks**: Validate outputs and file changes with string matching rules
- **Model Evaluation**: Use Claude to grade outputs against custom rubrics
- **Results Tracking**: Track evaluation history with automatic dashboards
- **Activity Logs**: Agentic tool calls and text snippets are captured per run in the JSON output
- **Per-Repository Isolation**: Each repo maintains its own evaluation results

## Installation

```bash
git clone <this-repo>
cd coe
pip install -e .
```

## Quick Start

### 1. Set Up Your Repository

In your repository root, create a tests/coe directory:

```bash
mkdir -p tests/coe
```

### 2. Create a .env File (in coe repo)

Configure credentials in the coe repository. Required for `runner: claude-code`; optional if you only use `runner: api` with credentials already in your shell environment:

```bash
cd ~/Repos/coe
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 3. Create an Evaluation Config

Create `tests/coe/my-prompt-eval.yml`:

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

### 4. Run Evaluations

From your repository root:

```bash
coe test
```

Run a specific evaluation:

```bash
coe test my-prompt-eval.yml
```

Specify number of runs:

```bash
coe test my-prompt-eval.yml -r 50
```

### 5. View the Dashboard

```bash
coe dashboard
```

Opens `tests/coe/results/index.html` in your default browser.

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
| `agentic` | Runs an SDK agentic loop. The model can call `read_file`, `write_file`, and `list_directory` tools across multiple turns. Use this for evals that require file manipulation. |

```yaml
runner: agentic
```

### agent_options

Options for the `agentic` runner. Ignored when `runner: api`.

```yaml
agent_options:
  max_turns: 15               # limit agentic turns (default: 10)
  allowed_tools:              # restrict which tools are available (default: all three)
    - read_file
    - list_directory
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
- `file_contains` / `file_does_not_contain` — match against a file on disk; `file` is relative to the repo root. Use these with `runner: claude-code` to verify the model actually changed the right files.

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
  rubric: |
    Grade 1-5 based on:
    - Relevance to prompt
    - Quality of reasoning

    Return JSON: {"score": <1-5>, "reasoning": "<brief explanation>"}
```

## Results

Results are saved to `tests/coe/results/`:

- `[timestamp].json` - Individual run results
- `index.html` - Interactive dashboard showing all results
- `static/` - Supporting assets for the dashboard

Open `tests/coe/results/index.html` in your browser to view the evaluation timeline.

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
  "logs": ["→ list_directory: src/", "✎ Here is what I found..."]
}
```

`logs` contains the activity from agentic runs (tool calls and text snippets). It is always present but empty for `runner: api`.

### Dashboard

The dashboard pass rate displayed on prompt cards, per-prompt stats, and the overview header is calculated over the **20 most recent runs** for each prompt, not the full history. All-time run counts are still shown for context.

## Example

See `example/sample-eval.yml` for a complete example with both runner types shown.

## License

MIT
