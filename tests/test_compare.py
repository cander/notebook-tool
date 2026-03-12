import json
from pathlib import Path

from notebook_tool.compare import (
    FIRST_FILE_COLOR,
    SECOND_FILE_COLOR,
    COLOR_RESET,
    compare_markdown_cells,
    render_report_with_names,
    sync_markdown_cells,
)


def _write_notebook(path: Path, cells: list[dict]) -> None:
    path.write_text(
        "\n".join(
            [
                "{",
                '  "cells": ' + json.dumps(cells),
                "}",
            ]
        ),
        encoding="utf-8",
    )


def test_compare_ignores_whitespace(tmp_path: Path) -> None:
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"

    _write_notebook(
        first,
        [
            {"cell_type": "markdown", "source": ["# Title\n", "Some text"]},
            {"cell_type": "code", "source": "print('x')"},
            {"cell_type": "markdown", "source": "A   b\n c"},
        ],
    )
    _write_notebook(
        second,
        [
            {"cell_type": "markdown", "source": "# Title\nSome text"},
            {"cell_type": "markdown", "source": "A b c"},
        ],
    )

    differences = compare_markdown_cells(first, second)
    assert differences == []


def test_compare_reports_differences(tmp_path: Path) -> None:
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"

    _write_notebook(
        first,
        [
            {"cell_type": "markdown", "source": "first"},
            {"cell_type": "markdown", "source": "second"},
        ],
    )
    _write_notebook(
        second,
        [
            {"cell_type": "markdown", "source": "first"},
            {"cell_type": "markdown", "source": "DIFFERENT"},
        ],
    )

    differences = compare_markdown_cells(first, second)
    assert len(differences) == 1
    assert differences[0].index == 2

    report = render_report_with_names(differences, first, second)
    assert "Cell 2 differs:" in report
    assert f"First file : {FIRST_FILE_COLOR}first.ipynb{COLOR_RESET}" in report
    assert f"Second file: {SECOND_FILE_COLOR}second.ipynb{COLOR_RESET}" in report
    assert f"{FIRST_FILE_COLOR}second{COLOR_RESET}" in report
    assert f"{SECOND_FILE_COLOR}DIFFERENT{COLOR_RESET}" in report
    assert "--- first.ipynb" not in report
    assert "+++ second.ipynb" not in report
    assert "- second" not in report
    assert "+ DIFFERENT" not in report


def test_sync_copy_first_to_second(tmp_path: Path) -> None:
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"
    _write_notebook(first, [{"cell_type": "markdown", "source": "from first"}])
    _write_notebook(second, [{"cell_type": "markdown", "source": "from second"}])

    choices = iter(["1"])
    sync_markdown_cells(first, second, input_fn=lambda _: next(choices), output_fn=lambda _: None)

    data = json.loads(second.read_text())
    assert data["cells"][0]["source"] == "from first"
    # First notebook unchanged
    data_first = json.loads(first.read_text())
    assert data_first["cells"][0]["source"] == "from first"


def test_sync_copy_second_to_first(tmp_path: Path) -> None:
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"
    _write_notebook(first, [{"cell_type": "markdown", "source": "from first"}])
    _write_notebook(second, [{"cell_type": "markdown", "source": "from second"}])

    choices = iter(["2"])
    sync_markdown_cells(first, second, input_fn=lambda _: next(choices), output_fn=lambda _: None)

    data = json.loads(first.read_text())
    assert data["cells"][0]["source"] == "from second"
    # Second notebook unchanged
    data_second = json.loads(second.read_text())
    assert data_second["cells"][0]["source"] == "from second"


def test_sync_skip(tmp_path: Path) -> None:
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"
    _write_notebook(first, [{"cell_type": "markdown", "source": "A"}, {"cell_type": "markdown", "source": "B"}])
    _write_notebook(second, [{"cell_type": "markdown", "source": "X"}, {"cell_type": "markdown", "source": "Y"}])

    # Skip first diff, copy second diff (1 → 2) 
    choices = iter(["s", "1"])
    sync_markdown_cells(first, second, input_fn=lambda _: next(choices), output_fn=lambda _: None)

    data = json.loads(second.read_text())
    assert data["cells"][0]["source"] == "X"  # skipped, unchanged
    assert data["cells"][1]["source"] == "B"  # copied from first


def test_sync_quit(tmp_path: Path) -> None:
    first = tmp_path / "first.ipynb"
    second = tmp_path / "second.ipynb"
    _write_notebook(first, [{"cell_type": "markdown", "source": "A"}, {"cell_type": "markdown", "source": "B"}])
    _write_notebook(second, [{"cell_type": "markdown", "source": "X"}, {"cell_type": "markdown", "source": "Y"}])

    # Quit immediately on first diff — neither notebook should be modified
    choices = iter(["q"])
    sync_markdown_cells(first, second, input_fn=lambda _: next(choices), output_fn=lambda _: None)

    data_first = json.loads(first.read_text())
    data_second = json.loads(second.read_text())
    assert data_first["cells"][0]["source"] == "A"
    assert data_second["cells"][0]["source"] == "X"
