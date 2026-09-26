"""Replay Engine for FORGE Telemetry Event Streams."""
from __future__ import annotations

import json
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class ReplayEngine:
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def replay_run(self, run_dir_or_file: Path | str, delay_sec: float = 0.1) -> None:
        target = Path(run_dir_or_file)
        if target.is_dir():
            events_file = target / "events.jsonl"
        else:
            events_file = target

        if not events_file.exists():
            self.console.print(f"[bold red]Replay file not found: {events_file}[/bold red]")
            return

        self.console.rule(f"[bold cyan]REPLAYING RUN: {events_file.parent.name}[/bold cyan]")

        with open(events_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                ev_type = data.get("event_type", "UNKNOWN")
                msg = data.get("message", "")
                ts = data.get("timestamp", "").split("T")[-1][:8]
                iter_no = data.get("iteration", 0)

                style = "green" if "COMPLETED" in ev_type else ("yellow" if "STARTED" in ev_type else "cyan")
                self.console.print(f"[dim]{ts}[/dim] (iter {iter_no}) [{style}]{ev_type:<22}[/{style}] {msg}")
                time.sleep(delay_sec)

        self.console.rule("[bold cyan]END OF REPLAY[/bold cyan]")
