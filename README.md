# coe - CLI Evaluation Framework

A lightweight CLI tool for testing and grading AI prompts using deterministic checks and model-based evaluation.

## Features

- **Easy Configuration**: Define evaluations in simple YAML files
- **Flexible Prompts**: Support inline prompts or file-based prompts
- **Deterministic Checks**: Validate outputs with string matching rules
- **Model Evaluation**: Use Claude to grade outputs against custom rubrics
- **Results Tracking**: Track evaluation history with automatic dashboards
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

### 2. Create a .env File (optional, in coe repo)

If you haven't already, configure credentials in the coe repository:

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

# Or file reference (relative to the .yml file)
prompt-under-eval: ../prompts/my-prompt.md
```

### model_for_eval

The Claude model to use for generation (e.g., `claude-haiku-5-5`)

### model_parameters

Parameters for the generation model:

```yaml
model_parameters:
  max_tokens: 1024
```

### test_input

Dictionary of inputs to pass to your prompt:

```yaml
test_input:
  user_question: What is AI?
  context: General knowledge
```

### deterministic_checks

Array of string matching checks:

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
```

### setup

Optional shell script to run before each evaluation run. Path is relative to the repo root.

```yaml
setup: scripts/reset_eval.sh
```

### model_evaluation

Optional Claude-based grading:

```yaml
model_evaluation:
  enabled: true
  model: claude-sonnet-5-5  # Optional; defaults to the generation model
  rubric: |
    Grade 1-5 based on:
    - Relevance to prompt
    - Quality of reasoning
```

## Results

Results are saved to `tests/coe/results/`:

- `[timestamp].json` - Individual run results
- `index.html` - Interactive dashboard showing all results
- `static/` - Supporting assets for the dashboard

Open `tests/coe/results/index.html` in your browser to view the evaluation timeline.

## Example

See `example/sample-eval.yml` for a complete example evaluation.

## License

MIT
