import json
import sys
from typing import Dict, Any
from anthropic import Anthropic

def _extract_text_from_response(response) -> str:
    for block in response.content:
        if hasattr(block, 'text'):
            return block.text
    return ''

def run_model_evaluation(
    output: str,
    prompt_text: str,
    test_input: Dict[str, Any],
    model_eval_config: Dict[str, Any],
    grader_model: str,
    client: Anthropic
) -> Dict[str, Any]:
    if not model_eval_config.get('enabled'):
        return None

    model = grader_model or model_eval_config.get('model', 'claude-haiku-4-5-20251001')
    rubric = model_eval_config.get('rubric', '')

    # Format test input for context
    test_input_str = "\n".join(f"{k}: {v}" for k, v in test_input.items()) if isinstance(test_input, dict) else str(test_input)

    prompt = f"""Please evaluate the following output based on the provided rubric and context.

ORIGINAL PROMPT:
{prompt_text}

TEST INPUT:
{test_input_str}

OUTPUT:
{output}

RUBRIC:
{rubric}

Respond with a JSON object containing:
- "score": an integer from 1-5
- "reasoning": a brief explanation of the score in less than 400 tokens.

Example format:
{{"score": 4, "reasoning": "..."}}
"""

    response = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    response_text = _extract_text_from_response(response)

    try:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            parsed = json.loads(json_str)
            score = parsed.get('score', 3)
            reasoning = parsed.get('reasoning', '')
        else:
            raise ValueError("No JSON found in response")
    except (json.JSONDecodeError, ValueError):
        score = 3
        reasoning = f"Failed to parse response: {response_text}"
        print(f"Model evaluation parsing failed. Full response:\n{response_text}", file=sys.stderr)

    score = max(1, min(5, score))
    pass_flag = score >= 4

    return {
        'enabled': True,
        'model': model,
        'score': score,
        'reasoning': reasoning,
        'pass': pass_flag
    }
