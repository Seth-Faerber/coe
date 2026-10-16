import yaml
import os
from pathlib import Path
from typing import Dict, Any, Tuple


def load_project_config(cwd: Path) -> Dict[str, Any]:
    """Load .coe.yml walking up from cwd to the repo root."""
    current = cwd if isinstance(cwd, Path) else Path(cwd)
    while current != current.parent:
        config_file = current / '.coe.yml'
        if config_file.exists():
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        if (current / '.git').exists():
            break
        current = current.parent
    return {}

def _find_repo_root(start_path: Path) -> Path:
    current = start_path if start_path.is_dir() else start_path.parent
    while current != current.parent:
        if (current / '.git').exists():
            return current
        current = current.parent
    return start_path.parent

VALID_RUNNERS = ('api', 'agentic')

VALID_AGENT_OPTIONS = {'max_turns', 'allowed_tools'}

REQUIRED_FIELDS = {
    'prompt-under-eval': (str,),
    'model_for_eval': (str,),
    'deterministic_checks': (list,),
}

OPTIONAL_FIELDS = {
    'test_input': (dict,),
    'model_parameters': (dict,),
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

    repo_root = _find_repo_root(yaml_path)
    config['_repo_root'] = repo_root

    config['_runner'] = config.get('runner', 'api')
    config['_agent_options'] = config.get('agent_options', {})

    if 'setup' in config:
        setup = config['setup']

        def _resolve(script: str) -> Path:
            p = Path(script).expanduser()
            return p if p.is_absolute() else repo_root / p

        config['_setup_before'] = _resolve(setup['before']) if 'before' in setup else None
        config['_setup_after'] = _resolve(setup['after']) if 'after' in setup else None
    else:
        config['_setup_before'] = None
        config['_setup_after'] = None

    return config

def validate_config(config: Dict[str, Any]) -> None:
    for field, field_types in REQUIRED_FIELDS.items():
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(config[field], field_types):
            type_names = ", ".join(t.__name__ for t in field_types)
            raise ValueError(f"Invalid type for {field}: expected {type_names}, got {type(config[field]).__name__}")

    for field, field_types in OPTIONAL_FIELDS.items():
        if field in config and not isinstance(config[field], field_types):
            type_names = ", ".join(t.__name__ for t in field_types)
            raise ValueError(f"Invalid type for {field}: expected {type_names}, got {type(config[field]).__name__}")

    if 'runner' in config:
        if config['runner'] not in VALID_RUNNERS:
            raise ValueError(f"Invalid runner: '{config['runner']}'. Must be one of: {', '.join(VALID_RUNNERS)}")

    if 'agent_options' in config:
        opts = config['agent_options']
        if not isinstance(opts, dict):
            raise ValueError("'agent_options' must be a dict")
        unknown = set(opts.keys()) - VALID_AGENT_OPTIONS
        if unknown:
            raise ValueError(f"'agent_options' has unknown keys: {', '.join(sorted(unknown))}")
        if 'max_turns' in opts and not isinstance(opts['max_turns'], int):
            raise ValueError("'agent_options.max_turns' must be an integer")
        if 'allowed_tools' in opts and not isinstance(opts['allowed_tools'], list):
            raise ValueError("'agent_options.allowed_tools' must be a list")
        VALID_TOOLS = {'read_file', 'write_file', 'list_directory', 'run_command'}
        if 'allowed_tools' in opts:
            unknown_tools = set(opts['allowed_tools']) - VALID_TOOLS
            if unknown_tools:
                raise ValueError(f"'agent_options.allowed_tools' has unknown tools: {', '.join(sorted(unknown_tools))}")

    for check in config['deterministic_checks']:
        if 'name' not in check or 'type' not in check or 'values' not in check:
            raise ValueError("Each deterministic check must have 'name', 'type', and 'values'")
        VALID_CHECK_TYPES = (
            'contains', 'does_not_contain',
            'file_contains', 'file_does_not_contain',
            'git_diff_contains', 'git_diff_does_not_contain',
        )
        if check['type'] not in VALID_CHECK_TYPES:
            raise ValueError(f"Invalid check type: {check['type']}")
        if check['type'] in ('file_contains', 'file_does_not_contain') and 'file' not in check:
            raise ValueError(
                f"Check '{check['name']}' with type '{check['type']}' must include a 'file' key"
            )

    if 'setup' in config:
        setup = config['setup']
        if not isinstance(setup, dict):
            raise ValueError("'setup' must be a dict with optional 'before' and/or 'after' keys")
        known_keys = {'before', 'after'}
        unknown = set(setup.keys()) - known_keys
        if unknown:
            raise ValueError(f"'setup' has unknown keys: {', '.join(sorted(unknown))}")
        if not setup:
            raise ValueError("'setup' must have at least one of 'before' or 'after'")
        for key in known_keys:
            if key in setup and not isinstance(setup[key], str):
                raise ValueError(f"'setup.{key}' must be a string (path to a script)")

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
    potential_path = Path(prompt_under_eval).expanduser()

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

def load_runtime_eval_config(yaml_path: str) -> Dict[str, Any]:
    """Load and validate a runtime eval YAML (evals/runtime/<skill>.yml)."""
    yaml_path = Path(yaml_path).resolve()

    if not yaml_path.exists():
        raise FileNotFoundError(f"Runtime eval file not found: {yaml_path}")

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"Empty or invalid YAML in {yaml_path}")

    if 'skill' not in config or not isinstance(config['skill'], str):
        raise ValueError("Runtime eval must have a 'skill' field (string)")
    if 'deterministic_checks' not in config or not isinstance(config['deterministic_checks'], list):
        raise ValueError("Runtime eval must have a 'deterministic_checks' list")

    for check in config['deterministic_checks']:
        if 'name' not in check or 'type' not in check or 'values' not in check:
            raise ValueError("Each deterministic check must have 'name', 'type', and 'values'")
        VALID_CHECK_TYPES = (
            'contains', 'does_not_contain',
            'file_contains', 'file_does_not_contain',
            'git_diff_contains', 'git_diff_does_not_contain',
        )
        if check['type'] not in VALID_CHECK_TYPES:
            raise ValueError(f"Invalid check type: {check['type']}")

    if 'model_evaluation' in config:
        me = config['model_evaluation']
        if not isinstance(me, dict):
            raise ValueError("model_evaluation must be a dict")
        if me.get('enabled') and 'rubric' not in me:
            raise ValueError("model_evaluation must include 'rubric' when enabled")
        if 'pass_threshold' in me and not isinstance(me['pass_threshold'], int):
            raise ValueError("model_evaluation.pass_threshold must be an integer")

    repo_root = _find_repo_root(yaml_path)
    config['_repo_root'] = repo_root
    config['_eval_file_path'] = yaml_path

    return config


def read_prompt_file(prompt_path: Path) -> str:
    with open(prompt_path, 'r') as f:
        return f.read()
