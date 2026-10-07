import yaml
import os
from pathlib import Path
from typing import Dict, Any, Tuple

def _find_repo_root(start_path: Path) -> Path:
    current = start_path if start_path.is_dir() else start_path.parent
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return start_path.parent

REQUIRED_FIELDS = {
    'prompt-under-eval': (str,),  # Can be inline text or file path
    'model_for_eval': str,
    'model_parameters': dict,
    'test_input': dict,
    'deterministic_checks': list,
}

def load_eval_config(yaml_path: str) -> Dict[str, Any]:
    yaml_path = Path(yaml_path).resolve()

    if not yaml_path.exists():
        raise FileNotFoundError(f"Eval file not found: {yaml_path}")

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"Empty or invalid YAML in {yaml_path}")

    validate_config(config)

    prompt_under_eval = config['prompt-under-eval']
    prompt_text, prompt_source = _resolve_prompt(prompt_under_eval, yaml_path)

    config['_prompt_text'] = prompt_text
    config['_prompt_source'] = prompt_source
    config['_eval_file_path'] = yaml_path
    config['_prompt_name'] = yaml_path.stem

    return config

def validate_config(config: Dict[str, Any]) -> None:
    for field, field_types in REQUIRED_FIELDS.items():
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(config[field], field_types):
            type_names = ", ".join(t.__name__ for t in field_types)
            raise ValueError(f"Invalid type for {field}: expected {type_names}, got {type(config[field]).__name__}")

    for check in config['deterministic_checks']:
        if 'name' not in check or 'type' not in check or 'values' not in check:
            raise ValueError("Each deterministic check must have 'name', 'type', and 'values'")
        if check['type'] not in ('contains', 'does_not_contain'):
            raise ValueError(f"Invalid check type: {check['type']}")

    if 'model_evaluation' in config:
        model_eval = config['model_evaluation']
        if not isinstance(model_eval, dict):
            raise ValueError("model_evaluation must be a dict")
        if model_eval.get('enabled') and 'rubric' not in model_eval:
            raise ValueError("model_evaluation must include 'rubric' when enabled")

def _resolve_prompt(prompt_under_eval: str, yaml_path: Path) -> Tuple[str, str]:
    """
    Resolve prompt-under-eval to actual prompt text.
    Returns (prompt_text, prompt_source) where source is 'inline' or 'file'.

    If prompt_under_eval looks like a file path and exists, read from file.
    Otherwise, treat it as inline prompt text.
    """
    # Check if it's a file path
    potential_path = Path(prompt_under_eval)

    # Handle relative paths relative to the yaml file directory
    if not potential_path.is_absolute():
        potential_path = yaml_path.parent / potential_path

    # If it looks like a file path and exists, read from file
    try:
        path_exists = potential_path.exists() and potential_path.is_file()
    except OSError:
        path_exists = False

    if path_exists:
        with open(potential_path, 'r') as f:
            prompt_text = f.read()
        return prompt_text, f"file: {potential_path}"

    # Otherwise, treat as inline prompt text
    return prompt_under_eval, "inline"

def read_prompt_file(prompt_path: Path) -> str:
    with open(prompt_path, 'r') as f:
        return f.read()
