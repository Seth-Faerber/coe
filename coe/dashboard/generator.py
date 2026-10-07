import json
import shutil
from pathlib import Path
from jinja2 import Template
from coe.storage.history_reader import read_all_results

TEMPLATES_DIR = Path(__file__).parent / 'templates'
STATIC_DIR = Path(__file__).parent / 'static'

def generate_dashboard(prompt_name: str, tests_coe_dir: Path) -> None:
    """
    Generate dashboard HTML files for the evaluation results.

    Args:
        prompt_name: Name of the prompt being evaluated
        tests_coe_dir: Path to tests/coe directory
    """
    results_dir = tests_coe_dir / 'results'

    _copy_static_files(results_dir)

    history = read_all_results(tests_coe_dir, prompt_name)

    # Generate single timeline/index HTML
    timeline_html = _generate_timeline_html(prompt_name, history)
    timeline_file = results_dir / 'index.html'
    with open(timeline_file, 'w') as f:
        f.write(timeline_html)

def _copy_static_files(results_dir: Path) -> None:
    """Copy static assets to results directory."""
    static_dest = results_dir / 'static'
    static_dest.mkdir(exist_ok=True)

    if STATIC_DIR.exists():
        for file in STATIC_DIR.glob('*'):
            if file.is_file():
                shutil.copy(file, static_dest / file.name)

def _generate_timeline_html(prompt_name: str, history: dict) -> str:
    """Generate the timeline/results HTML page."""
    reversed_results = list(reversed(history['results']))

    eval_data = {
        'prompt_name': prompt_name,
        'results': reversed_results,
        'changelog': history['changelog'],
        'pass_rate': f"{history['pass_rate']:.1f}%",
        'total_runs': history['total_runs'],
        'passed': history['passed'],
        'failed': history['failed']
    }

    template_path = TEMPLATES_DIR / 'prompt_timeline.html'
    with open(template_path, 'r') as f:
        template_str = f.read()

    template = Template(template_str)
    return template.render(
        prompt_name=prompt_name,
        eval_data_json=json.dumps(eval_data)
    )
