# Setting Up coe in Your Repository

This example shows how to set up the coe evaluation framework in your repository.

## Directory Structure

```
your-repo/
├── tests/
│   └── coe/
│       ├── my-prompt-eval.yml      # Your evaluation config
│       ├── another-prompt.yml      # Add as many as you want
│       └── results/                # Auto-generated results
│           ├── [timestamp].json    # Individual run results
│           ├── index.html          # Dashboard
│           └── static/             # Assets
├── prompts/                        # Optional: store prompts here
│   └── my-prompt.md
└── README.md
```

## Quick Setup

1. **Create tests/coe directory**:
   ```bash
   mkdir -p tests/coe
   ```

2. **Copy sample-eval.yml and modify it**:
   ```bash
   cp sample-eval.yml tests/coe/my-prompt-eval.yml
   # Edit as needed
   ```

3. **Run evaluations**:
   ```bash
   coe test
   ```

4. **View results**:
   ```bash
   coe dashboard
   ```

## Example Configurations

### Simple String Validation

```yaml
prompt-under-eval: Please respond with exactly "yes" or "no"

test-input:
  question: Is AI useful?

model_for_eval: claude-haiku-5-5
model_parameters:
  max_tokens: 100

deterministic_checks:
  - name: Valid response
    type: contains
    values:
      - "yes"
      - "no"
```

### With Model-Based Grading

```yaml
prompt-under-eval: ./prompts/creative-writing.md

test-input:
  genre: science fiction
  length: short story

model_for_eval: claude-haiku-5-5
model_parameters:
  max_tokens: 2048

deterministic_checks:
  - name: No spoilers in first paragraph
    type: does_not_contain
    values:
      - "SPOILER"
      - "spoiler"

model_evaluation:
  enabled: true
  rubric: |
    Grade 1-5 on:
    - Creativity and originality
    - Adherence to genre
    - Writing quality
```

## Multiple Evaluations

Create multiple `.yml` files in `tests/coe/`:

```
tests/coe/
├── prompt-1-eval.yml
├── prompt-2-eval.yml
└── prompt-3-eval.yml
```

Then run all at once:
```bash
coe test
```

Or run specific ones:
```bash
coe test prompt-1-eval.yml
```

## Tips

- Use relative paths for prompts: `../prompts/my-prompt.md`
- Store prompts in markdown files for readability
- Use meaningful check names - they appear in results
- Run 20-30 times for statistical validity
- Check the HTML dashboard to spot patterns in failures
