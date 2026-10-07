import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

def write_result(result: Dict[str, Any], prompt_name: str, tests_coe_dir: Path) -> Path:
    """
    Write evaluation result to tests/coe/results/ directory.

    Args:
        result: The evaluation result dictionary
        prompt_name: Name of the prompt (used for organizing results)
        tests_coe_dir: Path to tests/coe directory

    Returns:
        Path to the written result file
    """
    results_dir = tests_coe_dir / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)

    result_with_name = {'prompt_name': prompt_name, **result}

    now = datetime.now().isoformat().replace(':', '-').replace('.', '-')
    result_file = results_dir / f"{now}.json"

    with open(result_file, 'w') as f:
        json.dump(result_with_name, f, indent=2)

    return result_file
