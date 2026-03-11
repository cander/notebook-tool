from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarkdownDifference:
    index: int
    first_text: str
    second_text: str


def _extract_markdown_cells(notebook_path: Path) -> list[str]:
    try:
        data = json.loads(notebook_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Notebook not found: {notebook_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in notebook: {notebook_path}") from exc

    cells = data.get("cells")
    if not isinstance(cells, list):
        raise ValueError(f"Notebook missing 'cells' list: {notebook_path}")

    markdown_cells: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        if cell.get("cell_type") != "markdown":
            continue

        source = cell.get("source", "")
        if isinstance(source, list):
            markdown_cells.append("".join(str(part) for part in source))
        elif isinstance(source, str):
            markdown_cells.append(source)
        else:
            markdown_cells.append(str(source))

    return markdown_cells


def _normalize_for_compare(text: str, ignore_whitespace: bool) -> str:
    if not ignore_whitespace:
        return text
    # Collapse all whitespace runs to a single space to ignore formatting differences.
    return re.sub(r"\s+", " ", text).strip()


def compare_markdown_cells(
    first_notebook: Path,
    second_notebook: Path,
    *,
    ignore_whitespace: bool = True,
) -> list[MarkdownDifference]:
    first_cells = _extract_markdown_cells(first_notebook)
    second_cells = _extract_markdown_cells(second_notebook)

    max_len = max(len(first_cells), len(second_cells))
    differences: list[MarkdownDifference] = []

    for idx in range(max_len):
        first_text = first_cells[idx] if idx < len(first_cells) else ""
        second_text = second_cells[idx] if idx < len(second_cells) else ""

        first_compare = _normalize_for_compare(first_text, ignore_whitespace)
        second_compare = _normalize_for_compare(second_text, ignore_whitespace)

        if first_compare != second_compare:
            differences.append(
                MarkdownDifference(
                    index=idx + 1,
                    first_text=first_text,
                    second_text=second_text,
                )
            )

    return differences


def render_report(differences: list[MarkdownDifference]) -> str:
    # Backward-compatible wrapper for callers that do not pass notebook names.
    return render_report_with_names(differences, "first_notebook", "second_notebook")


def render_report_with_names(
    differences: list[MarkdownDifference],
    first_notebook: str | Path,
    second_notebook: str | Path,
) -> str:
    if not differences:
        return "No Markdown differences found."

    first_label = Path(first_notebook).name
    second_label = Path(second_notebook).name

    lines = [f"Found {len(differences)} Markdown difference(s):"]
    for diff in differences:
        lines.append("")
        lines.append(f"Cell {diff.index} differs:")
        unified = difflib.unified_diff(
            diff.first_text.splitlines(),
            diff.second_text.splitlines(),
            fromfile=first_label,
            tofile=second_label,
            lineterm="",
        )
        diff_lines = list(unified)
        if diff_lines:
            lines.extend(diff_lines)
        else:
            lines.append("(Difference detected after normalization; raw line diff is empty.)")

    return "\n".join(lines)
