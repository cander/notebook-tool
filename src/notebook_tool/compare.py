from __future__ import annotations

import ast
import difflib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


FIRST_FILE_COLOR = "\033[31m"
SECOND_FILE_COLOR = "\033[32m"
COLOR_RESET = "\033[0m"


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


def _code_cells(data: dict) -> list[dict]:
    code_cells: list[dict] = []
    for cell in data["cells"]:
        if isinstance(cell, dict) and cell.get("cell_type") == "code":
            code_cells.append(cell)
    return code_cells


def _source_to_text(source: object) -> str:
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    if isinstance(source, str):
        return source
    return str(source)


def _matrix_from_payload(payload: object) -> list[list[str]] | None:
    if isinstance(payload, list):
        if not payload:
            return []
        if all(isinstance(row, list) for row in payload):
            return [[str(cell) for cell in row] for row in payload]
        if all(isinstance(row, dict) for row in payload):
            first_row = payload[0]
            columns = list(first_row.keys())
            return [[str(row.get(col, "")) for col in columns] for row in payload]
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            matrix = _matrix_from_payload(payload["data"])
            if matrix is not None:
                return matrix
        if "values" in payload and isinstance(payload["values"], list):
            matrix = _matrix_from_payload(payload["values"])
            if matrix is not None:
                return matrix
    return None


def _matrix_from_text(text: str) -> list[list[str]] | None:
    stripped = text.strip()
    if not stripped:
        return None

    # First try literal Python list-like output (for example, [[1, 2], [3, 4]]).
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        parsed = None
    if parsed is not None:
        matrix = _matrix_from_payload(parsed)
        if matrix is not None:
            return matrix

    # Fallback for plain-text tabular output like pandas' text/plain representation.
    lines = [line.rstrip() for line in stripped.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    rows: list[list[str]] = []
    for line in lines[1:]:
        if not re.match(r"^\s*\d+", line):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        rows.append(parts[1:])

    if not rows:
        return None

    width = len(rows[0])
    if any(len(row) != width for row in rows):
        return None

    return rows


def _output_to_matrix(output: object) -> list[list[str]] | None:
    if not isinstance(output, dict):
        return None

    data = output.get("data")
    if isinstance(data, dict):
        for mime in ("application/json", "application/vnd.dataresource+json"):
            if mime in data:
                matrix = _matrix_from_payload(data[mime])
                if matrix is not None:
                    return matrix

        if "text/plain" in data:
            matrix = _matrix_from_text(_source_to_text(data["text/plain"]))
            if matrix is not None:
                return matrix

    if "text" in output:
        matrix = _matrix_from_text(_source_to_text(output["text"]))
        if matrix is not None:
            return matrix

    return None


def _tabular_output_matrices(outputs: object) -> list[list[list[str]]]:
    if not isinstance(outputs, list):
        return []

    matrices: list[list[list[str]]] = []
    for output in outputs:
        matrix = _output_to_matrix(output)
        if matrix is not None:
            matrices.append(matrix)
    return matrices


def _grade_output_matrices(
    key_matrix: list[list[str]],
    student_matrix: list[list[str]],
    *,
    code_cell_index: int,
    output_index: int,
) -> str | None:
    location = f"Code cell {code_cell_index}, output {output_index}"

    if len(key_matrix) != len(student_matrix):
        return (
            f"{location}: row count mismatch "
            f"(key={len(key_matrix)}, notebook={len(student_matrix)})."
        )

    if not key_matrix:
        return f"{location}: output has no rows to grade."

    key_cols = len(key_matrix[0])
    student_cols = len(student_matrix[0]) if student_matrix else 0
    if key_cols != student_cols:
        return (
            f"{location}: column count mismatch "
            f"(key={key_cols}, notebook={student_cols})."
        )

    if key_cols == 0:
        return f"{location}: output has no columns to grade."

    checks = [
        ("first cell of first row", key_matrix[0][0], student_matrix[0][0]),
        ("last cell of first row", key_matrix[0][-1], student_matrix[0][-1]),
        ("first cell of last row", key_matrix[-1][0], student_matrix[-1][0]),
        ("last cell of last row", key_matrix[-1][-1], student_matrix[-1][-1]),
    ]

    for label, expected, actual in checks:
        if expected.strip() != actual.strip():
            return (
                f"{location}: {label} mismatch "
                f"(key={expected!r}, notebook={actual!r})."
            )

    return None


def grade_notebook_outputs(key_notebook: Path, notebook_to_grade: Path) -> tuple[bool, str]:
    key_data = _load_notebook(key_notebook)
    student_data = _load_notebook(notebook_to_grade)

    key_code_cells = _code_cells(key_data)
    student_code_cells = _code_cells(student_data)

    if len(key_code_cells) != len(student_code_cells):
        return (
            False,
            "Code cell count mismatch "
            f"(key={len(key_code_cells)}, notebook={len(student_code_cells)}).",
        )

    for code_idx, key_cell in enumerate(key_code_cells, start=1):
        student_cell = student_code_cells[code_idx - 1]

        key_outputs = key_cell.get("outputs", [])
        student_outputs = student_cell.get("outputs", [])
        key_matrices = _tabular_output_matrices(key_outputs)
        student_matrices = _tabular_output_matrices(student_outputs)

        if len(key_matrices) != len(student_matrices):
            return (
                False,
                f"Code cell {code_idx}: tabular output count mismatch "
                f"(key={len(key_matrices)}, notebook={len(student_matrices)}).",
            )

        for output_idx, key_matrix in enumerate(key_matrices, start=1):
            student_matrix = student_matrices[output_idx - 1]

            message = _grade_output_matrices(
                key_matrix,
                student_matrix,
                code_cell_index=code_idx,
                output_index=output_idx,
            )
            if message:
                return False, message

    return True, "Notebook matches key output checks."


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


def _colorize(label: str, color: str) -> str:
    return f"{color}{label}{COLOR_RESET}"


def _format_diff(first_text: str, second_text: str, first_label: str, second_label: str) -> list[str]:
    ndiff_lines = list(difflib.ndiff(first_text.splitlines(), second_text.splitlines()))
    if not ndiff_lines:
        return []

    content_lines: list[str] = []
    for line in ndiff_lines:
        if line.startswith("? "):
            continue
        if line.startswith("- "):
            content_lines.append(_colorize(line[2:], FIRST_FILE_COLOR))
            continue
        if line.startswith("+ "):
            content_lines.append(_colorize(line[2:], SECOND_FILE_COLOR))
            continue
        if line.startswith("  "):
            content_lines.append(line[2:])

    return [
        f"First file : {_colorize(first_label, FIRST_FILE_COLOR)}",
        f"Second file: {_colorize(second_label, SECOND_FILE_COLOR)}",
        *content_lines,
    ]


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
    first_label_colored = _colorize(first_label, FIRST_FILE_COLOR)
    second_label_colored = _colorize(second_label, SECOND_FILE_COLOR)

    first_modified = False
    second_modified = False

    max_len = max(len(first_map), len(second_map))
    for md_idx in range(max_len):
        first_cell_idx, first_text = first_map[md_idx] if md_idx < len(first_map) else (None, "")
        second_cell_idx, second_text = second_map[md_idx] if md_idx < len(second_map) else (None, "")

        if _normalize_for_compare(first_text, ignore_whitespace) == _normalize_for_compare(second_text, ignore_whitespace):
            continue

        output_fn(f"\nMarkdown cell {md_idx + 1} differs:")
        diff_lines = _format_diff(first_text, second_text, first_label, second_label)
        if diff_lines:
            output_fn("\n".join(diff_lines))
        else:
            output_fn("(Difference detected after normalization; raw line diff is empty.)")

        output_fn(f"\n  [1] Copy {first_label_colored} \u2192 {second_label_colored}")
        output_fn(f"  [2] Copy {second_label_colored} \u2192 {first_label_colored}")
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
        output_fn(f"\nWrote changes to {first_label_colored}")
    if second_modified:
        _write_notebook(second_path, second_data)
        output_fn(f"\nWrote changes to {second_label_colored}")
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
        diff_lines = _format_diff(diff.first_text, diff.second_text, first_label, second_label)
        if diff_lines:
            lines.extend(diff_lines)
        else:
            lines.append("(Difference detected after normalization; raw line diff is empty.)")

    return "\n".join(lines)
