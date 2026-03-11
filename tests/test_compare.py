import json
from pathlib import Path

from notebook_tool.compare import compare_markdown_cells, render_report_with_names


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
    assert "--- first.ipynb" in report
    assert "+++ second.ipynb" in report
