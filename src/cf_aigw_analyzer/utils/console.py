"""Rich-powered console helpers.

Centralising the console here lets CLI code print without each call site
importing ``rich`` directly, and lets tests swap the console for capture.
"""

from __future__ import annotations

from functools import lru_cache

from rich.console import Console


@lru_cache(maxsize=1)
def get_console() -> Console:
    """Return a process-wide :class:`rich.console.Console`."""

    return Console(soft_wrap=False, highlight=False)


def print_kv(title: str, data: dict[str, object]) -> None:
    """Pretty-print a section title followed by key/value lines."""

    console = get_console()
    console.rule(title)
    width = max((len(str(key)) for key in data), default=0)
    for key, value in data.items():
        console.print(f"  [bold]{str(key).ljust(width)}[/bold]  {value}")
