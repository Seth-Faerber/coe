import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import List
from anthropic import Anthropic
from dotenv import load_dotenv

from coe.config.yaml_loader import load_eval_config
from coe.evaluators.deterministic import run_deterministic_checks
from coe.evaluators.model_grader import run_model_evaluation
from coe.storage.results_writer import write_result
from coe.storage.changelog_manager import add_change_log_entry
from coe.storage.history_reader import read_all_results
from coe.dashboard.generator import generate_dashboard

def _find_tests_coe_dir() -> Path:
    """Find tests/coe directory starting from current directory going up."""
    current = Path.cwd()
    while current != current.parent:
        tests_coe = current / 'tests' / 'coe'
        if tests_coe.exists() and tests_coe.is_dir():
            return tests_coe
        current = current.parent
    raise RuntimeError("Could not find tests/coe directory. Are you in the right repository?")

def _discover_eval_files(tests_coe_dir: Path) -> List[Path]:
    """Discover all .yml files in tests/coe directory."""
    return sorted(tests_coe_dir.glob('*.yml'))

def _format_test_input(test_input: dict) -> str:
    """Format test input dictionary for the prompt."""
    if isinstance(test_input, str):
        return test_input
    lines = []
    for key, value in test_input.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)

def run_eval(eval_file: Path, num_runs: int = 20, tests_coe_dir: Path = None):
    """Run an evaluation."""
    if tests_coe_dir is None:
        tests_coe_dir = _find_tests_coe_dir()

    config = load_eval_config(str(eval_file))
    prompt_name = config['_prompt_name']
    prompt_text = config['_prompt_text']
    prompt_source = config['_prompt_source']

    test_input = config['test_input']
    model = config['model_for_eval']
    model_params = config['model_parameters']

    api_key = os.environ.get('ANTHROPIC_AUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')
    base_url = os.environ.get('ANTHROPIC_BASE_URL')

    client = Anthropic(api_key=api_key, base_url=base_url)

    passed_count = 0
    failed_count = 0

    print(f"Running {num_runs} evals for '{prompt_name}'...")
    print(f"  Prompt source: {prompt_source}")

    for i in range(1, num_runs + 1):
        start_time = datetime.now()
        test_input_str = _format_test_input(test_input)

        messages = [
            {
                "role": "user",
                "content": f"{prompt_text}\n\n---\n\n{test_input_str}",
            }
        ]

        response = client.messages.create(
            model=model,
            max_tokens=model_params.get('max_tokens', 1024),
            messages=messages,
        )

        output = response.content[0].text
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        det_results = run_deterministic_checks(output, config['deterministic_checks'])
        det_passed = all(check_result['overall_pass'] for check_result in det_results.values())

        model_eval_results = None
        if config.get('model_evaluation', {}).get('enabled'):
            # Use the model specified in model_evaluation config, or haiku as default
            grader_model = config['model_evaluation'].get('model', model)
            model_eval_results = run_model_evaluation(
                output,
                prompt_text,
                test_input,
                config['model_evaluation'],
                grader_model,
                client,
            )

        overall_passed = det_passed
        if model_eval_results:
            overall_passed = overall_passed and (model_eval_results['score'] >= 4)

        if overall_passed:
            passed_count += 1
        else:
            failed_count += 1

        result = {
            'test_input': test_input,
            'output': output,
            'deterministic_checks': det_results,
            'model_evaluation': model_eval_results,
            'passed': overall_passed,
            'duration_seconds': duration,
            'timestamp': datetime.now().isoformat(),
        }

        write_result(result, prompt_name, tests_coe_dir)

        status = "✓ PASS" if overall_passed else "✗ FAIL"
        print(f"  [{i}/{num_runs}] {status}")

    print(f"\nResults: {passed_count}/{num_runs} passed ({100*passed_count//num_runs}%)")
    generate_dashboard(prompt_name, tests_coe_dir)

def cmd_test(args):
    """Handle 'coe test' command."""
    # Load .env from coe package directory
    coe_dir = Path(__file__).parent.parent
    env_file = coe_dir / '.env'
    if env_file.exists():
        load_dotenv(env_file)

    tests_coe_dir = _find_tests_coe_dir()

    if args.eval_file:
        # Run specific evaluation
        eval_path = tests_coe_dir / args.eval_file
        if not eval_path.exists():
            print(f"Error: Evaluation file not found: {eval_path}")
            sys.exit(1)
        run_eval(eval_path, args.runs, tests_coe_dir)
    else:
        # Discover and run all evaluations
        eval_files = _discover_eval_files(tests_coe_dir)
        if not eval_files:
            print(f"No .yml files found in {tests_coe_dir}")
            sys.exit(1)

        print(f"Found {len(eval_files)} evaluation(s)")
        for eval_file in eval_files:
            print(f"\nRunning {eval_file.name}...")
            run_eval(eval_file, args.runs, tests_coe_dir)

def main():
    parser = argparse.ArgumentParser(description='coe - CLI evaluation framework')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    test_parser = subparsers.add_parser('test', help='Run evaluations')
    test_parser.add_argument('eval_file', nargs='?', help='Specific .yml file to run (optional; runs all if omitted)')
    test_parser.add_argument('-r', '--runs', type=int, default=20, help='Number of evaluation runs (default: 20)')
    test_parser.set_defaults(func=cmd_test)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)

if __name__ == '__main__':
    main()
