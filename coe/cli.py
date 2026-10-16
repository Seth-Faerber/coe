import sys
import os
import argparse
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List
from anthropic import Anthropic
from dotenv import load_dotenv

from coe.config.yaml_loader import load_eval_config, load_project_config, load_runtime_eval_config
from coe.evaluators.deterministic import run_deterministic_checks
from coe.evaluators.model_grader import run_model_evaluation
from coe.storage.results_writer import write_result
from coe.dashboard.generator import generate_full_dashboard

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_RESET = "\033[0m"

def _run_script(path: Path, cwd: Path) -> None:
    result = subprocess.run(["bash", str(path)], cwd=str(cwd), stdin=subprocess.DEVNULL)
    if result.returncode != 0:
        print(f"  Script failed (exit {result.returncode}): {path.name}. Aborting.")
        sys.exit(1)

_READ_FILE_TOOL = {
    "name": "read_file",
    "description": "Read the content of a file from disk.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the working directory"},
        },
        "required": ["path"],
    },
}

_WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write content to a file, creating or overwriting it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the working directory"},
            "content": {"type": "string", "description": "Full file content to write"},
        },
        "required": ["path", "content"],
    },
}

_LIST_DIR_TOOL = {
    "name": "list_directory",
    "description": "List the files and subdirectories in a directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path relative to the working directory"},
        },
        "required": ["path"],
    },
}

_RUN_COMMAND_TOOL = {
    "name": "run_command",
    "description": "Run a shell command in the working directory and return its stdout, stderr, and exit code.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to run, e.g. 'bd list --status=open' or 'bd show beads-123'",
            },
        },
        "required": ["command"],
    },
}

_AVAILABLE_TOOLS = {
    "list_directory": _LIST_DIR_TOOL,
    "read_file": _READ_FILE_TOOL,
    "write_file": _WRITE_FILE_TOOL,
    "run_command": _RUN_COMMAND_TOOL,
}


def _execute_tool(name: str, input_dict: dict, cwd: Path) -> str:
    try:
        if name == "list_directory":
            entries = sorted((cwd / input_dict["path"]).iterdir(), key=lambda p: (p.is_file(), p.name))
            return "\n".join((e.name + "/" if e.is_dir() else e.name) for e in entries)
        if name == "read_file":
            return (cwd / input_dict["path"]).read_text()
        if name == "write_file":
            target = cwd / input_dict["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(input_dict["content"])
            return "ok"
        if name == "run_command":
            result = subprocess.run(
                input_dict["command"], shell=True, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, cwd=str(cwd), timeout=30
            )
            return f"exit_code: {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"


_MAX_TOOL_RESULT_CHARS = 20_000  # ~5k tokens; prevents a single large file from blowing up context

def _run_with_tools(prompt: str, model: str, options: dict, cwd: Path, client: Anthropic, log_collector: list = None, model_params: dict = None) -> tuple[str, bool]:
    allowed = options.get("allowed_tools", list(_AVAILABLE_TOOLS.keys()))
    tools = [_AVAILABLE_TOOLS[t] for t in allowed if t in _AVAILABLE_TOOLS]
    max_turns = options.get("max_turns", 10)
    max_tokens = (model_params or {}).get("max_tokens", 8096)

    messages = [{"role": "user", "content": prompt}]
    final_text = ""
    turn_count = 0

    for _ in range(max_turns):
        turn_count += 1
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            tools=tools,
            messages=messages,
        )

        for block in response.content:
            if hasattr(block, "text"):
                final_text = block.text
                snippet = block.text.strip()
                if snippet:
                    msg = f"    ✎ {snippet[:100]}"
                    print(msg, flush=True)
                    if log_collector is not None:
                        log_collector.append(msg.strip())
            elif block.type == "tool_use":
                preview = block.input.get("command") or block.input.get("path") or next(iter(block.input.values()), "")
                msg = f"    → {block.name}: {str(preview)[:80]}"
                print(msg, flush=True)
                if log_collector is not None:
                    log_collector.append(msg.strip())

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _execute_tool(block.name, block.input, cwd)
                    if len(result) > _MAX_TOOL_RESULT_CHARS:
                        result = result[:_MAX_TOOL_RESULT_CHARS] + f"\n... [truncated — {len(result)} chars total]"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    if log_collector is not None:
        log_collector.append(f"ℹ {turn_count} turn(s)")

    return final_text, False, turn_count

def _resolve_eval_dir(dir_override: str = None) -> Path:
    """Resolve the eval directory from --dir flag, .coe.yml, convention, or fallback."""
    cwd = Path.cwd()

    if dir_override:
        p = Path(dir_override).expanduser()
        if not p.is_absolute():
            p = cwd / p
        if not p.exists():
            raise RuntimeError(f"Specified eval directory not found: {p}")
        return p

    project_config = load_project_config(cwd)
    if project_config.get('eval_dir'):
        rel = Path(project_config['eval_dir']).expanduser()
        current = cwd
        while current != current.parent:
            candidate = current / rel
            if candidate.exists() and candidate.is_dir():
                return candidate
            if (current / '.git').exists():
                return current / rel  # return even if not yet created
            current = current.parent

    current = cwd
    while current != current.parent:
        p = current / 'evals' / 'promotion'
        if p.exists() and p.is_dir():
            return p
        current = current.parent

    current = cwd
    while current != current.parent:
        p = current / 'tests' / 'coe'
        if p.exists() and p.is_dir():
            return p
        current = current.parent

    raise RuntimeError(
        "Could not find an eval directory. "
        "Create evals/promotion/, set eval_dir in .coe.yml, or use --dir."
    )


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

    test_input = config.get('test_input')
    model = config['model_for_eval']
    model_params = config.get('model_parameters', {})
    runner = config.get('_runner', 'api')

    api_key = os.environ.get('ANTHROPIC_AUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')
    base_url = os.environ.get('ANTHROPIC_BASE_URL')

    passed_count = 0
    failed_count = 0
    error_count = 0

    print(f"Running {num_runs} evals for '{prompt_name}'...")
    print(f"  Prompt source: {prompt_source}")
    print(f"  Runner: {runner}")

    for i in range(1, num_runs + 1):
        if config.get('_setup_before'):
            _run_script(config['_setup_before'], config['_repo_root'])

        start_time = datetime.now()
        content = prompt_text
        if test_input:
            content = f"{prompt_text}\n\n---\n\n{_format_test_input(test_input)}"

        eval_client = Anthropic(api_key=api_key, base_url=base_url)
        log_collector = []
        num_turns = None
        if runner == 'agentic':
            output, _, num_turns = _run_with_tools(
                content,
                model,
                config.get('_agent_options', {}),
                config['_repo_root'],
                eval_client,
                log_collector=log_collector,
                model_params=model_params,
            )
        else:
            messages = [{"role": "user", "content": content}]
            response = eval_client.messages.create(
                model=model,
                max_tokens=model_params.get('max_tokens', 1024),
                messages=messages,
            )
            output = next((block.text for block in response.content if hasattr(block, 'text')), '')

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        det_results = run_deterministic_checks(output, config['deterministic_checks'], config.get('_repo_root'))
        det_passed = all(check_result['overall_pass'] for check_result in det_results.values())

        model_eval_results = None
        if config.get('model_evaluation', {}).get('enabled'):
            model_eval_config = config['model_evaluation']
            grader_model = model_eval_config.get('model', model)
            file_content = None
            graded_file = model_eval_config.get('graded_file')
            if graded_file and config.get('_repo_root'):
                graded_path = Path(config['_repo_root']) / graded_file
                if graded_path.exists():
                    file_content = graded_path.read_text()
            model_eval_results = run_model_evaluation(
                output,
                prompt_text,
                test_input,
                model_eval_config,
                grader_model,
                file_content=file_content,
            )

        overall_error = bool(model_eval_results and model_eval_results.get('error'))
        if overall_error:
            overall_passed = None
            error_count += 1
        else:
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
            'error': overall_error,
            'duration_seconds': duration,
            'timestamp': datetime.now().isoformat(),
            'num_turns': num_turns,
            'logs': log_collector,
        }

        write_result(result, prompt_name, tests_coe_dir)

        if config.get('_setup_after'):
            _run_script(config['_setup_after'], config['_repo_root'])

        if overall_error:
            status = f"{_YELLOW}⚠ ERROR{_RESET}"
        elif overall_passed:
            status = f"{_GREEN}✓ PASS{_RESET}"
        else:
            status = f"{_RED}✗ FAIL{_RESET}"
        print(f"  [{i}/{num_runs}] {status}")

    non_error = num_runs - error_count
    pct = (100 * passed_count // non_error) if non_error else 0
    error_suffix = f" · {error_count} error{'s' if error_count != 1 else ''}" if error_count else ""
    print(f"\nResults: {passed_count}/{non_error} passed ({pct}%){error_suffix}")
    generate_full_dashboard(tests_coe_dir)

def cmd_dashboard(args):
    """Handle 'coe dashboard' command — optionally rebuild, then open index.html."""
    eval_dir = _resolve_eval_dir()
    should_build = getattr(args, 'action', None) == 'build' or getattr(args, 'build_flag', False)
    if should_build:
        generate_full_dashboard(eval_dir)
        print("Dashboard rebuilt.")
    index_path = (eval_dir / 'results' / 'index.html').resolve()
    if not index_path.exists():
        print("No dashboard found. Run 'coe promote' first to generate results.")
        sys.exit(1)
    url = index_path.as_uri()
    webbrowser.open(url)
    print(f"Opening {index_path}")

def cmd_promote(args):
    """Handle 'coe promote' command."""
    coe_dir = Path(__file__).parent.parent
    env_file = coe_dir / '.env'
    if env_file.exists():
        load_dotenv(env_file)

    os.environ['COE_MODE'] = 'promotion'

    eval_dir = _resolve_eval_dir(getattr(args, 'dir', None))

    if args.eval_file:
        eval_path = eval_dir / args.eval_file
        if not eval_path.exists():
            print(f"Error: Evaluation file not found: {eval_path}")
            sys.exit(1)
        run_eval(eval_path, args.runs, eval_dir)
    else:
        eval_files = _discover_eval_files(eval_dir)
        if not eval_files:
            print(f"No .yml files found in {eval_dir}")
            sys.exit(1)

        print(f"Found {len(eval_files)} evaluation(s)")
        for eval_file in eval_files:
            print(f"\nRunning {eval_file.name}...")
            run_eval(eval_file, args.runs, eval_dir)


def cmd_test_deprecated(args):
    """Deprecated alias for 'coe promote'."""
    print(f"{_YELLOW}Warning: 'coe test' is deprecated. Use 'coe promote' instead.{_RESET}", file=sys.stderr)
    cmd_promote(args)


def _resolve_runtime_eval_dir(project_config: dict) -> Path:
    rel = Path(project_config.get('runtime_eval_dir', 'evals/runtime'))
    current = Path.cwd()
    while current != current.parent:
        candidate = current / rel
        if candidate.exists() and candidate.is_dir():
            return candidate
        if (current / '.git').exists():
            return current / rel
        current = current.parent
    return Path.cwd() / rel


def _hook_log(runtime_eval_dir: Path, skill_name, event: str) -> None:
    try:
        import json as _json
        log_path = runtime_eval_dir / '.coe-hook.log'
        entry = _json.dumps({'ts': datetime.now().isoformat(), 'skill': skill_name, 'event': event})
        with open(log_path, 'a') as f:
            f.write(entry + '\n')
    except Exception:
        pass


def cmd_runtime_check(args):
    """Handle 'coe runtime-check' command — grade a skill's output in real time."""
    import json
    import time

    coe_dir = Path(__file__).parent.parent
    env_file = coe_dir / '.env'
    if env_file.exists():
        load_dotenv(env_file)

    skill_name = getattr(args, 'skill', None)
    from_hook = getattr(args, 'from_hook', False)

    # Resolve early so _hook_log can write even before the skill name is known
    project_config = load_project_config(Path.cwd())
    runtime_eval_dir = _resolve_runtime_eval_dir(project_config)

    if from_hook:
        try:
            hook_data = json.loads(sys.stdin.read())
            if hook_data.get('tool_name') != 'Skill':
                _hook_log(runtime_eval_dir, skill_name, 'wrong_tool')
                sys.exit(0)
            skill_name = hook_data.get('tool_input', {}).get('skill') or skill_name
        except Exception:
            _hook_log(runtime_eval_dir, skill_name, 'stdin_error')
            sys.exit(0)

    if not skill_name:
        print("No skill name. Use --skill SKILL_NAME or --from-hook.", file=sys.stderr)
        sys.exit(1)

    config_path = runtime_eval_dir / f"{skill_name}.yml"

    if not config_path.exists():
        _hook_log(runtime_eval_dir, skill_name, 'no_config')
        sys.exit(0)

    try:
        config = load_runtime_eval_config(str(config_path))
    except Exception as e:
        _hook_log(runtime_eval_dir, skill_name, 'config_error')
        print(f"Error loading runtime eval config: {e}", file=sys.stderr)
        sys.exit(0)

    repo_root = config['_repo_root']

    sentinel_path = runtime_eval_dir / f".coe-sentinel-{skill_name}"

    retry_count = 0
    if sentinel_path.exists():
        try:
            retry_count = json.loads(sentinel_path.read_text()).get('retries', 0)
        except Exception:
            retry_count = 0

    retry_count += 1
    sentinel_path.write_text(json.dumps({'retries': retry_count, 'skill': skill_name}))

    _start = time.monotonic()
    det_results = run_deterministic_checks('', config['deterministic_checks'], repo_root)
    det_passed = all(r['overall_pass'] for r in det_results.values())

    model_eval_config = config.get('model_evaluation', {})
    model_eval_results = None
    diff = ''
    if model_eval_config.get('enabled'):
        grader_model = model_eval_config.get('model', 'claude-haiku-4-5-20251001')
        diff = subprocess.run(
            ['git', 'diff', 'HEAD'], cwd=str(repo_root), capture_output=True, text=True
        ).stdout
        model_eval_results = run_model_evaluation(
            output=diff,
            prompt_text=f"Runtime evaluation of skill: {skill_name}",
            test_input={},
            model_eval_config=model_eval_config,
            grader_model=grader_model,
        )

    pass_threshold = model_eval_config.get('pass_threshold', 4)
    overall_passed = det_passed
    if model_eval_results and not model_eval_results.get('error'):
        overall_passed = overall_passed and (model_eval_results['score'] >= pass_threshold)

    _duration = time.monotonic() - _start
    write_result(
        {
            'output': diff,
            'deterministic_checks': det_results,
            'model_evaluation': model_eval_results,
            'passed': overall_passed,
            'duration_seconds': round(_duration, 3),
            'timestamp': datetime.now().isoformat(),
            'retry_count': retry_count,
        },
        skill_name,
        runtime_eval_dir,
    )

    if overall_passed:
        sentinel_path.unlink(missing_ok=True)
        _hook_log(runtime_eval_dir, skill_name, 'pass')
        print(f"  {_GREEN}✓ Runtime eval passed{_RESET} for skill '{skill_name}' (attempt {retry_count})")
        sys.exit(0)

    lines = [f"Runtime eval FAILED for skill '{skill_name}' (attempt {retry_count}/3)", ""]
    for check_name, result in det_results.items():
        marker = "✓" if result['overall_pass'] else "✗"
        lines.append(f"  {marker} {check_name}")
        if not result['overall_pass']:
            if result.get('error'):
                lines.append(f"      Error: {result['error']}")
            for c in result['checks']:
                if not c['passed']:
                    verb = "missing" if 'contains' in result['type'] else "unexpectedly present"
                    lines.append(f"      Value {verb}: {c['value']!r}")

    if model_eval_results:
        score = model_eval_results.get('score')
        reasoning = model_eval_results.get('reasoning', '')
        lines.append(f"  Model eval score: {score}/5 (pass threshold: {pass_threshold})")
        if reasoning:
            lines.append(f"  Reasoning: {reasoning}")

    lines.append("")

    if retry_count >= 3:
        sentinel_path.unlink(missing_ok=True)
        _hook_log(runtime_eval_dir, skill_name, 'escalate')
        header = "HUMAN ESCALATION REQUIRED: skill has failed 3 consecutive runtime evaluations."
        lines = [header, "Do not retry automatically. A human must review the output.", ""] + lines
        lines.append("Session halted after 3 failed attempts.")
    else:
        _hook_log(runtime_eval_dir, skill_name, 'fail')
        remaining = 3 - retry_count
        lines.append(f"Please review the issues above and retry the skill. ({remaining} attempt(s) remaining)")

    print(json.dumps({"decision": "block", "reason": "\n".join(lines)}))
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description='coe - CLI evaluation framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  coe promote                     run all promotion evals (also: coe p)
  coe promote my-eval.yml         run a single promotion eval
  coe promote my-eval.yml -r 5   run 5 times instead of the default 20
  coe promote --dir evals/promotion/  run evals from a specific directory
  coe dashboard                   open the results dashboard (also: coe dash, coe d)
  coe dash build                  rebuild dashboard from existing results, then open (also: --build, -b)

eval directory resolution (in order):
  1. --dir PATH flag
  2. eval_dir key in .coe.yml at the repo root
  3. evals/promotion/ if it exists
  4. tests/coe/ (legacy fallback)

prompt tips:
  In your YAML eval file, prompt-under-eval can be an inline string or a
  relative file path -- if the path exists on disk, coe reads its contents.
""",
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    _promote_epilog = """
prompt-under-eval in your YAML can be an inline string or a relative file path.
If the path resolves to an existing file, coe reads its contents as the prompt.

setup:
  before: scripts/before.sh  # optional; runs before each model call
  after: scripts/after.sh    # optional; runs after each result is written

runner: agentic               # optional; runs an SDK agentic tool loop instead of a single API call
agent_options:
  max_turns: 15
  allowed_tools:
    - read_file
    - write_file
    - list_directory
    - run_command         # runs shell commands; required for bd/beads and other CLIs
"""

    promote_parser = subparsers.add_parser(
        'promote',
        aliases=['p'],
        help='Run promotion evaluations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_promote_epilog,
    )
    promote_parser.add_argument('eval_file', nargs='?', help='YAML filename to run (omit to run all)')
    promote_parser.add_argument('-r', '--runs', type=int, default=20, help='Number of evaluation runs (default: 20)')
    promote_parser.add_argument('--dir', dest='dir', metavar='PATH', help='Eval directory (overrides .coe.yml and convention)')
    promote_parser.set_defaults(func=cmd_promote)

    test_parser = subparsers.add_parser(
        'test',
        help='(deprecated) Alias for coe promote',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_promote_epilog,
    )
    test_parser.add_argument('eval_file', nargs='?', help='YAML filename to run (omit to run all)')
    test_parser.add_argument('-r', '--runs', type=int, default=20, help='Number of evaluation runs (default: 20)')
    test_parser.add_argument('--dir', dest='dir', metavar='PATH', help='Eval directory (overrides .coe.yml and convention)')
    test_parser.set_defaults(func=cmd_test_deprecated)

    runtime_parser = subparsers.add_parser(
        'runtime-check',
        help='Grade a skill\'s output in real time (used by PostToolUse hook)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Loads evals/runtime/<skill-name>.yml, runs deterministic + model checks, and manages
a sentinel file to track retries. Exit codes: 0=pass, 2=fail (feedback or escalation).

examples:
  coe runtime-check --skill update-claude-md
  coe runtime-check --from-hook          # reads skill name from stdin (PostToolUse JSON)
""",
    )
    runtime_parser.add_argument('--skill', metavar='SKILL_NAME', help='Name of the skill to evaluate')
    runtime_parser.add_argument('--from-hook', dest='from_hook', action='store_true',
                                help='Read skill name from PostToolUse stdin JSON')
    runtime_parser.set_defaults(func=cmd_runtime_check)

    dashboard_parser = subparsers.add_parser(
        'dashboard',
        aliases=['dash', 'd'],
        help='Open the results dashboard in the default browser',
    )
    dashboard_parser.add_argument(
        'action',
        nargs='?',
        choices=['build'],
        help="'build' to regenerate the dashboard from existing result files, then open it",
    )
    dashboard_parser.add_argument(
        '--build', '-b',
        dest='build_flag',
        action='store_true',
        help='Regenerate the dashboard from existing result files, then open it',
    )
    dashboard_parser.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)

if __name__ == '__main__':
    main()
