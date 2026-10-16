import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

FILE_CHECK_TYPES = ('file_contains', 'file_does_not_contain')
GIT_DIFF_CHECK_TYPES = ('git_diff_contains', 'git_diff_does_not_contain')

def _git_diff(repo_root: Path) -> str:
    result = subprocess.run(
        ['git', 'diff', 'HEAD'],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout

def run_deterministic_checks(
    output: str,
    checks: List[Dict[str, Any]],
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    results = {}
    _diff_cache: Optional[str] = None

    for check in checks:
        check_name = check['name']
        check_type = check['type']
        values = check['values']

        if check_type in FILE_CHECK_TYPES:
            file_path = Path(check['file'])
            if not file_path.is_absolute() and repo_root:
                file_path = repo_root / file_path
            try:
                target = file_path.read_text()
            except FileNotFoundError:
                results[check_name] = {
                    'type': check_type,
                    'checks': [{'value': v, 'passed': False} for v in values],
                    'overall_pass': False,
                    'error': f"File not found: {file_path}",
                }
                continue
        elif check_type in GIT_DIFF_CHECK_TYPES:
            if repo_root is None:
                results[check_name] = {
                    'type': check_type,
                    'checks': [{'value': v, 'passed': False} for v in values],
                    'overall_pass': False,
                    'error': 'git_diff checks require a repo_root',
                }
                continue
            if _diff_cache is None:
                _diff_cache = _git_diff(repo_root)
            target = _diff_cache
        else:
            target = output

        check_results = []
        for value in values:
            if check_type in ('contains', 'file_contains', 'git_diff_contains'):
                passed = value.lower() in target.lower()
            else:
                passed = value.lower() not in target.lower()
            check_results.append({'value': value, 'passed': passed})

        results[check_name] = {
            'type': check_type,
            'checks': check_results,
            'overall_pass': all(r['passed'] for r in check_results),
        }

    return results
