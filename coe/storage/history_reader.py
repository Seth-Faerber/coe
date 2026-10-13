import json
from pathlib import Path
from typing import List, Dict, Any
from coe.storage.changelog_manager import load_changelog

def read_all_results(tests_coe_dir: Path, prompt_name: str = None) -> Dict[str, Any]:
    """
    Read results from tests/coe/results/ directory, optionally filtered by prompt name.

    Args:
        tests_coe_dir: Path to tests/coe directory
        prompt_name: Filter to only results with this prompt_name field

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
        if prompt_name and result.get('prompt_name') != prompt_name:
            continue
        results.append(result)

    results.sort(key=lambda x: x.get('timestamp', ''))

    changelog = load_changelog(tests_coe_dir) if prompt_name else []

    recent = results[-20:]
    recent_passed = sum(1 for r in recent if r.get('passed', False))
    recent_runs = len(recent)
    pass_rate = (recent_passed / recent_runs * 100) if recent_runs else 0

    passed_count = sum(1 for r in results if r.get('passed', False))

    annotated_results = _annotate_with_changes(results, changelog)

    return {
        'prompt_name': prompt_name or 'evaluation',
        'results': annotated_results,
        'changelog': changelog,
        'pass_rate': pass_rate,
        'total_runs': len(results),
        'passed': passed_count,
        'failed': len(results) - passed_count,
        'recent_passed': recent_passed,
        'recent_runs': recent_runs,
    }


def read_all_prompts_results(tests_coe_dir: Path) -> List[Dict[str, Any]]:
    """
    Read results for every distinct prompt_name found in the results directory.

    Returns a list of per-prompt summary dicts, each including the full results array.
    Prompts are returned in alphabetical order by name.
    """
    results_dir = tests_coe_dir / 'results'
    if not results_dir.exists():
        return []

    prompt_names: set = set()
    for json_file in sorted(results_dir.glob('*.json')):
        if json_file.name == 'changelog.json':
            continue
        with open(json_file, 'r') as f:
            try:
                result = json.load(f)
            except Exception:
                continue
        name = result.get('prompt_name')
        if name:
            prompt_names.add(name)

    return [read_all_results(tests_coe_dir, name) for name in sorted(prompt_names)]

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
