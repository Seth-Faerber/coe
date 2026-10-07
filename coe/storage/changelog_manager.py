import json
from pathlib import Path
from datetime import datetime

def add_change_log_entry(tests_coe_dir: Path, description: str) -> None:
    """
    Add entry to changelog in tests/coe/results/changelog.json.

    Args:
        tests_coe_dir: Path to tests/coe directory
        description: Description of the change
    """
    results_dir = tests_coe_dir / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)

    changelog_file = results_dir / 'changelog.json'

    if changelog_file.exists():
        with open(changelog_file, 'r') as f:
            changelog = json.load(f)
    else:
        changelog = []

    entry = {
        'timestamp': datetime.now().isoformat() + 'Z',
        'description': description
    }

    changelog.append(entry)

    with open(changelog_file, 'w') as f:
        json.dump(changelog, f, indent=2)

def load_changelog(tests_coe_dir: Path) -> list:
    """
    Load changelog from tests/coe/results/changelog.json.

    Args:
        tests_coe_dir: Path to tests/coe directory

    Returns:
        List of changelog entries
    """
    changelog_file = tests_coe_dir / 'results' / 'changelog.json'

    if not changelog_file.exists():
        return []

    with open(changelog_file, 'r') as f:
        return json.load(f)
