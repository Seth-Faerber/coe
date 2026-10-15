import json
import shutil
from pathlib import Path
from jinja2 import Template
from coe.storage.history_reader import read_all_prompts_results

TEMPLATES_DIR = Path(__file__).parent / 'templates'
STATIC_DIR = Path(__file__).parent / 'static'

def generate_full_dashboard(tests_coe_dir: Path) -> None:
    """Generate the multi-prompt dashboard HTML."""
    results_dir = tests_coe_dir / 'results'
    _copy_static_files(results_dir)

    all_prompt_data = read_all_prompts_results(tests_coe_dir)

    all_prompts = [
        {
            'prompt_name': p['prompt_name'],
            'pass_rate': f"{p['pass_rate']:.1f}%",
            'total_runs': p['total_runs'],
            'passed': p['passed'],
            'failed': p['failed'],
            'recent_passed': p['recent_passed'],
            'recent_runs': p['recent_runs'],
        }
        for p in all_prompt_data
    ]

    prompts = [
        {
            'prompt_name': p['prompt_name'],
            'results': list(reversed(p['results'])),
            'changelog': p['changelog'],
            'pass_rate': f"{p['pass_rate']:.1f}%",
            'total_runs': p['total_runs'],
            'passed': p['passed'],
            'failed': p['failed'],
            'recent_runs': p['recent_runs'],
        }
        for p in all_prompt_data
    ]

    dashboard_data = {
        'all_prompts': all_prompts,
        'prompts': prompts,
    }

    template_path = TEMPLATES_DIR / 'prompt_timeline.html'
    with open(template_path, 'r') as f:
        template_str = f.read()

    template = Template(template_str)
    html = template.render(dashboard_data_json=json.dumps(dashboard_data))

    with open(results_dir / 'index.html', 'w') as f:
        f.write(html)

def _copy_static_files(results_dir: Path) -> None:
    static_dest = results_dir / 'static'
    static_dest.mkdir(exist_ok=True)

    if STATIC_DIR.exists():
        for file in STATIC_DIR.glob('*'):
            if file.is_file():
                shutil.copy(file, static_dest / file.name)
