"""FORGE Command Line Interface."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from rich.console import Console

from forge.benchmark.ablations import AblationStudy
from forge.benchmark.cases import SAMPLE_BENCHMARK_TASKS
from forge.benchmark.runner import BenchmarkRunner
from forge.models.llm import LiveLLMProvider
from forge.models.mock import MockModelProvider
from forge.orchestrator.engine import Orchestrator
from forge.ui.replay import ReplayEngine
from forge.ui.tui import ForgeUI


console = Console()


def run_command(args: argparse.Namespace) -> int:
    """Execute the core FORGE autonomous/interactive agent loop."""
    issue_text = ""
    
    # 1. Read from --issue argument if provided
    if args.issue:
        issue_path = Path(args.issue)
        if issue_path.is_file():
            issue_text = issue_path.read_text(encoding="utf-8")
        else:
            issue_text = args.issue

    # 2. Check standard input if not a TTY (piped or redirected from evaluator)
    elif not sys.stdin.isatty():
        issue_text = sys.stdin.read().strip()

    # 3. Interactive prompt fallback
    if not issue_text:
        console.print("[bold cyan]FORGE Self-Verifying Agent[/bold cyan]")
        console.print("Please enter the issue description or task (Ctrl+D to finish):")
        try:
            issue_text = sys.stdin.read().strip()
        except KeyboardInterrupt:
            return 1

    if not issue_text:
        console.print("[yellow]No issue provided. Running sample self-check task...[/yellow]")
        issue_text = "Verify project repository structure and run self-test suite."

    # Initialize model provider based on AI_API_KEY
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            model = LiveLLMProvider(api_key=api_key)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not initialize LiveLLMProvider ({e}). Falling back to Mock.[/yellow]")
            model = MockModelProvider()
    else:
        console.print("[dim][NOTICE] No AI_API_KEY detected. Running with deterministic verification harness.[/dim]")
        model = MockModelProvider()

    ui = ForgeUI(console=console)
    orchestrator = Orchestrator(
        root_path=Path(".").resolve(),
        model_provider=model,
        max_iterations=args.max_iterations,
        ui=ui,
    )

    state = orchestrator.run_task(issue_text, task_id=args.task_id)
    return 0 if state.status.value in {"COMPLETED", "INSUFFICIENT_EVIDENCE"} else 1


def benchmark_command(args: argparse.Namespace) -> int:
    """Run baseline vs FORGE comparative benchmark."""
    runner = BenchmarkRunner(console=console)
    runner.run_suite(SAMPLE_BENCHMARK_TASKS)
    
    study = AblationStudy(console=console)
    study.run_ablations()
    return 0


def replay_command(args: argparse.Namespace) -> int:
    """Replay an agent run from event telemetry."""
    replay = ReplayEngine(console=console)
    replay.replay_run(args.run_path, delay_sec=args.delay)
    return 0


def inspect_command(args: argparse.Namespace) -> int:
    """Inspect the output report and state of a completed run."""
    run_dir = Path(args.run_path)
    report_file = run_dir / "report.md" if run_dir.is_dir() else run_dir
    if not report_file.exists():
        console.print(f"[red]Report not found: {report_file}[/red]")
        return 1

    content = report_file.read_text(encoding="utf-8")
    from rich.markdown import Markdown
    console.print(Markdown(content))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="FORGE: Self-Verifying AI Software Engineer Harness",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # forge run
    run_parser = subparsers.add_parser("run", help="Run the autonomous agent on an issue")
    run_parser.add_argument("--issue", "-i", type=str, help="Path to issue file or issue string")
    run_parser.add_argument("--task-id", "-t", type=str, default=None, help="Custom task ID")
    run_parser.add_argument("--max-iterations", "-m", type=int, default=10, help="Max iterations")
    run_parser.add_argument("--autonomous", "-a", action="store_true", default=True, help="Run autonomously")

    # forge benchmark
    subparsers.add_parser("benchmark", help="Run comparative benchmark and ablation studies")

    # forge replay
    replay_parser = subparsers.add_parser("replay", help="Replay a previous task execution")
    replay_parser.add_argument("run_path", type=str, help="Path to run directory or events.jsonl")
    replay_parser.add_argument("--delay", type=float, default=0.08, help="Delay between events")

    # forge inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect report of a completed run")
    inspect_parser.add_argument("run_path", type=str, help="Path to run directory or report.md")

    args = parser.parse_args()

    if args.command == "run" or args.command is None:
        if args.command is None:
            # Default to run if no command specified
            args = run_parser.parse_args(sys.argv[1:])
        sys.exit(run_command(args))
    elif args.command == "benchmark":
        sys.exit(benchmark_command(args))
    elif args.command == "replay":
        sys.exit(replay_command(args))
    elif args.command == "inspect":
        sys.exit(inspect_command(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
