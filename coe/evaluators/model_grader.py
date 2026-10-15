import os
from typing import Dict, Any, Optional
from anthropic import Anthropic

_EVAL_TOOL = {
    "name": "submit_evaluation",
    "description": "Submit the evaluation score and reasoning",
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer", "minimum": 1, "maximum": 5},
            "reasoning": {"type": "string", "description": "Brief explanation in under 400 tokens"}
        },
        "required": ["score", "reasoning"]
    }
}

def run_model_evaluation(
    output: str,
    prompt_text: str,
    test_input: Dict[str, Any],
    model_eval_config: Dict[str, Any],
    grader_model: str,
    file_content: Optional[str] = None,
) -> Dict[str, Any]:
    if not model_eval_config.get('enabled'):
        return None

    api_key = os.environ.get('ANTHROPIC_AUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')
    base_url = os.environ.get('ANTHROPIC_BASE_URL')
    client = Anthropic(api_key=api_key, base_url=base_url)

    model = grader_model or model_eval_config.get('model', 'claude-haiku-4-5-20251001')
    rubric = model_eval_config.get('rubric', '')

    test_input_str = "\n".join(f"{k}: {v}" for k, v in test_input.items()) if isinstance(test_input, dict) else str(test_input)

    output_section = (
        f"GRADED FILE CONTENT (final state after agent run):\n{file_content}"
        if file_content is not None
        else f"OUTPUT:\n{output}"
    )

    prompt = f"""Evaluate the following output based on the rubric. Call submit_evaluation with your score and reasoning.

ORIGINAL PROMPT:
{prompt_text}

TEST INPUT:
{test_input_str}

{output_section}

RUBRIC:
{rubric}
"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            tools=[_EVAL_TOOL],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": prompt}]
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_evaluation":
                score = max(1, min(5, int(block.input["score"])))
                reasoning = block.input["reasoning"]
                return {
                    'enabled': True,
                    'model': model,
                    'score': score,
                    'reasoning': reasoning,
                    'pass': score >= 4,
                }

        return {
            'enabled': True,
            'error': True,
            'error_detail': 'Grader returned no tool call',
            'pass': None,
        }

    except Exception as e:
        return {
            'enabled': True,
            'error': True,
            'error_detail': str(e),
            'pass': None,
        }
