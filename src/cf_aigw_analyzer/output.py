"""Local output helpers."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable

DEFAULT_COLUMNS = (
    "log_id",
    "created_at",
    "provider",
    "model",
    "model_type",
    "success",
    "cached",
    "status_code",
    "tokens_in",
    "tokens_out",
    "duration_ms",
    "latency_ms",
    "generation_ms",
    "usage_input_tokens",
    "usage_output_tokens",
    "usage_cached_tokens",
    "usage_reasoning_tokens",
    "usage_fetch_status",
)


def sanitize_output_rows(
    rows: list[dict[str, Any]],
    include_raw_json: bool = False,
    include_scope: bool = False,
) -> list[dict[str, Any]]:
    """Remove fields that are useful locally but risky in shareable exports."""

    excluded = set()
    if not include_raw_json:
        excluded.add("raw_json")
    if not include_scope:
        excluded.update({"account_id", "gateway_id"})
    return [{key: value for key, value in row.items() if key not in excluded} for row in rows]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def print_table(rows: list[dict[str, Any]], columns: Iterable[str] = DEFAULT_COLUMNS) -> None:
    columns = [column for column in columns if rows and column in rows[0]]
    if not rows:
        print("(no rows)")
        return
    if not columns:
        columns = list(rows[0].keys())

    display_rows = []
    widths = {column: len(column) for column in columns}
    for row in rows:
        display = {}
        for column in columns:
            value = _stringify(row.get(column))
            if len(value) > 48:
                value = value[:45] + "..."
            display[column] = value
            widths[column] = max(widths[column], len(value))
        display_rows.append(display)

    print(" | ".join(column.ljust(widths[column]) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))
    for row in display_rows:
        print(" | ".join(row[column].ljust(widths[column]) for column in columns))


def write_json(rows: list[dict[str, Any]], output: str | None) -> None:
    text = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def write_csv(rows: list[dict[str, Any]], output: str | None) -> None:
    if not rows:
        text = ""
        if output:
            Path(output).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return

    fieldnames = sorted({key for row in rows for key in row.keys()})
    if output:
        with Path(output).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return

    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def emit_rows(
    rows: list[dict[str, Any]],
    fmt: str,
    output: str | None = None,
    include_raw_json: bool = False,
    include_scope: bool = False,
) -> None:
    rows = sanitize_output_rows(rows, include_raw_json=include_raw_json, include_scope=include_scope)
    if fmt == "json":
        write_json(rows, output)
    elif fmt == "csv":
        write_csv(rows, output)
    elif fmt == "table":
        if output:
            write_csv(rows, output)
        else:
            print_table(rows)
    else:
        raise ValueError(f"unsupported output format: {fmt}")
