from typing import Dict, List, Any

def run_deterministic_checks(output: str, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = {}

    for check in checks:
        check_name = check['name']
        check_type = check['type']
        values = check['values']

        check_results = []
        for value in values:
            if check_type == 'contains':
                passed = value.lower() in output.lower()
            elif check_type == 'does_not_contain':
                passed = value.lower() not in output.lower()
            else:
                passed = False

            check_results.append({
                'value': value,
                'passed': passed
            })

        overall_pass = all(r['passed'] for r in check_results)

        results[check_name] = {
            'type': check_type,
            'checks': check_results,
            'overall_pass': overall_pass
        }

    return results
