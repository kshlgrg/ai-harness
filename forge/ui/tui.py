"""Rich Terminal UI Dashboard for FORGE Live State and Telemetry."""
from __future__ import annotations

import sys
from typing import Optional
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from forge.state.events import ForgeEvent
from forge.state.state import TaskState


class ForgeUI:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.events_buffer: list[str] = []
        self.is_interactive = sys.stdout.isatty()

    def handle_event(self, event: ForgeEvent) -> None:
        formatted = f"[dim]{event.timestamp.split('T')[-1][:8]}[/dim] [cyan]{event.event_type.value}[/cyan]: {event.message}"
        self.events_buffer.append(formatted)
        if len(self.events_buffer) > 12:
            self.events_buffer.pop(0)

        if not self.is_interactive:
            # Piped / Headless mode: print clean single lines for evaluator logs
            self.console.print(f"[{event.event_type.value}] {event.message}")

    def render_dashboard(self, state: TaskState) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3),
        )

        # Header
        header_text = Text(
            f"  FORGE — SELF-VERIFYING AI SOFTWARE ENGINEER   |   TASK: {state.task_id}   |   ITER: {state.iteration}/{state.max_iterations}   |   STATE: {state.status.value}",
            style="bold white on blue",
        )
        layout["header"].update(Panel(header_text))

        # Main split: left = requirements & status, right = event stream
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )

        # Requirements table
        req_table = Table(title="Requirements & Acceptance", expand=True)
        req_table.add_column("ID", style="cyan", width=10)
        req_table.add_column("Description", style="white")
        req_table.add_column("Status", style="magenta", width=12)

        for req in state.requirements[:8]:
            status_style = "green" if req.status.value == "VERIFIED" else "yellow"
            req_table.add_row(req.id, req.description[:40] + ("..." if len(req.description) > 40 else ""), f"[{status_style}]{req.status.value}[/{status_style}]")

        layout["left"].update(Panel(req_table, title="Traceability Matrix"))

        # Events stream panel
        event_lines = "\n".join(self.events_buffer) if self.events_buffer else "[dim]No events yet...[/dim]"
        layout["right"].update(Panel(Text.from_markup(event_lines), title="Live Event Telemetry"))

        # Footer
        test_info = state.test_results.get("summary", {})
        tests_passed = test_info.get("passed", 0)
        tests_total = test_info.get("total", 0)
        strategy = state.current_strategy
        footer_msg = f" Tests Passed: {tests_passed}/{tests_total}  |  Active Strategy: {strategy}  |  Modified Files: {len(state.files_modified)}  |  Checkpoints: {len(state.checkpoints)}"
        layout["footer"].update(Panel(Text(footer_msg, style="dim white on black")))

        return layout

    def print_final_summary(self, state: TaskState, diff: str) -> None:
        evidence = state.evidence or state.calculate_evidence()
        self.console.print("\n")
        self.console.rule("[bold green]FORGE EXECUTION COMPLETE[/bold green]")
        self.console.print(f"[bold]Task:[/bold] {state.task_id} - {state.objective}")
        self.console.print(f"[bold]Status:[/bold] {state.status.value}")
        self.console.print(f"[bold]Evidence Confidence:[/bold] {evidence.confidence_score * 100:.1f}%")
        self.console.print(f"[bold]Requirements Satisfied:[/bold] {evidence.requirements_satisfied}/{evidence.total_requirements}")
        self.console.print(f"[bold]Tests Passed:[/bold] {evidence.tests_passed}/{evidence.total_tests}")
        self.console.print(f"[bold]Critic Verdict:[/bold] {'[green]PASS[/green]' if evidence.critic_passed else '[red]FAIL[/red]'}")
        self.console.print(f"[bold]Files Changed:[/bold] {', '.join(state.files_modified) or 'None'}")
        
        if diff.strip():
            self.console.print("\n[bold cyan]Patch Summary:[/bold cyan]")
            self.console.print(f"Total diff lines: {len(diff.splitlines())}")
        self.console.rule()
