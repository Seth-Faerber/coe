import json
from pathlib import Path
from typing import List, Dict, Any
from coe.storage.changelog_manager import load_changelog

def read_all_results(tests_coe_dir: Path, prompt_name: str = None) -> Dict[str, Any]:
    """
    Read all results from tests/coe/results/ directory.

    Args:
        tests_coe_dir: Path to tests/coe directory
        prompt_name: Optional filter by prompt name (not used in flat structure)

    Returns:
        Dictionary with results, changelog, and statistics
    """
    results_dir = tests_coe_dir / 'results'

    if not results_dir.exists():
        return {
            'prompt_name': prompt_name or 'unknown',
            'results': [],
            'changelog': [],
            'pass_rate': 0,
            'total_runs': 0,
            'passed': 0,
            'failed': 0
        }

    results = []
    for json_file in sorted(results_dir.glob('*.json')):
        if json_file.name == 'changelog.json':
            continue
        with open(json_file, 'r') as f:
            result = json.load(f)
            results.append(result)

    # Sort by file creation time (filename is timestamp-based)
    results.sort(key=lambda x: x.get('timestamp', ''))

    changelog = load_changelog(tests_coe_dir) if prompt_name else []

    passed_count = sum(1 for r in results if r.get('passed', False))
    pass_rate = (passed_count / len(results) * 100) if results else 0

    annotated_results = _annotate_with_changes(results, changelog)

    return {
        'prompt_name': prompt_name or 'evaluation',
        'results': annotated_results,
        'changelog': changelog,
        'pass_rate': pass_rate,
        'total_runs': len(results),
        'passed': passed_count,
        'failed': len(results) - passed_count
    }

def _annotate_with_changes(results: List[Dict], changelog: List[Dict]) -> List[Dict]:
    """Annotate results with changelog markers."""
    result_copies = [result.copy() for result in results]
    for result_copy in result_copies:
        result_copy['change_marker'] = None

    for change in changelog:
        for result_copy in result_copies:
            if result_copy.get('change_marker') is None and result_copy.get('timestamp', '') > change.get('timestamp', ''):
                result_copy['change_marker'] = change
                break

    return result_copies
