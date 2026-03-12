from __future__ import annotations

import difflib
import json
import re
from collections.abc import Callable
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


def _load_notebook(notebook_path: Path) -> dict:
    try:
        data = json.loads(notebook_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Notebook not found: {notebook_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in notebook: {notebook_path}") from exc
    if not isinstance(data.get("cells"), list):
        raise ValueError(f"Notebook missing 'cells' list: {notebook_path}")
    return data


def _markdown_cell_map(data: dict) -> list[tuple[int, str]]:
    """Returns (cells-array index, text) for each markdown cell."""
    result: list[tuple[int, str]] = []
    for i, cell in enumerate(data["cells"]):
        if not isinstance(cell, dict) or cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            text = "".join(str(p) for p in source)
        elif isinstance(source, str):
            text = source
        else:
            text = str(source)
        result.append((i, text))
    return result


def _write_notebook(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def sync_markdown_cells(
    first_path: Path,
    second_path: Path,
    *,
    ignore_whitespace: bool = True,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    """Interactively synchronize Markdown cells between two notebooks."""
    first_data = _load_notebook(first_path)
    second_data = _load_notebook(second_path)
    first_map = _markdown_cell_map(first_data)
    second_map = _markdown_cell_map(second_data)

    first_label = first_path.name
    second_label = second_path.name

    first_modified = False
    second_modified = False

    max_len = max(len(first_map), len(second_map))
    for md_idx in range(max_len):
        first_cell_idx, first_text = first_map[md_idx] if md_idx < len(first_map) else (None, "")
        second_cell_idx, second_text = second_map[md_idx] if md_idx < len(second_map) else (None, "")

        if _normalize_for_compare(first_text, ignore_whitespace) == _normalize_for_compare(second_text, ignore_whitespace):
            continue

        output_fn(f"\nMarkdown cell {md_idx + 1} differs:")
        diff_lines = list(difflib.unified_diff(
            first_text.splitlines(),
            second_text.splitlines(),
            fromfile=first_label,
            tofile=second_label,
            lineterm="",
        ))
        if diff_lines:
            output_fn("\n".join(diff_lines))
        else:
            output_fn("(Difference detected after normalization; raw line diff is empty.)")

        output_fn(f"\n  [1] Copy {first_label} \u2192 {second_label}")
        output_fn(f"  [2] Copy {second_label} \u2192 {first_label}")
        output_fn( "  [s] Skip")
        output_fn( "  [q] Quit")

        while True:
            choice = input_fn("Choice: ").strip().lower()
            if choice in ("1", "2", "s", "q"):
                break
            output_fn("Please enter 1, 2, s, or q.")

        if choice == "q":
            break
        elif choice == "s":
            continue
        elif choice == "1":
            first_source = first_data["cells"][first_cell_idx]["source"] if first_cell_idx is not None else ""
            if second_cell_idx is not None:
                second_data["cells"][second_cell_idx]["source"] = first_source
            else:
                second_data["cells"].append({"cell_type": "markdown", "metadata": {}, "source": first_source})
            second_modified = True
        elif choice == "2":
            second_source = second_data["cells"][second_cell_idx]["source"] if second_cell_idx is not None else ""
            if first_cell_idx is not None:
                first_data["cells"][first_cell_idx]["source"] = second_source
            else:
                first_data["cells"].append({"cell_type": "markdown", "metadata": {}, "source": second_source})
            first_modified = True

    if first_modified:
        _write_notebook(first_path, first_data)
        output_fn(f"\nWrote changes to {first_label}")
    if second_modified:
        _write_notebook(second_path, second_data)
        output_fn(f"\nWrote changes to {second_label}")
    if not first_modified and not second_modified:
        output_fn("\nNo changes made.")


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
