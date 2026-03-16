import json
from pathlib import Path

from notebook_tool.compare import (
    FIRST_FILE_COLOR,
    SECOND_FILE_COLOR,
    COLOR_RESET,
    compare_markdown_cells,
    grade_notebook_outputs,
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


def test_grade_notebook_outputs_passes(tmp_path: Path) -> None:
    key = tmp_path / "key.ipynb"
    student = tmp_path / "student.ipynb"

    _write_notebook(
        key,
        [
            {
                "cell_type": "code",
                "source": "answer",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[1, 2], [3, 4]]},
                    }
                ],
            }
        ],
    )
    _write_notebook(
        student,
        [
            {
                "cell_type": "code",
                "source": "answer",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[1, 2], [3, 4]]},
                    }
                ],
            }
        ],
    )

    passed, message = grade_notebook_outputs(key, student)
    assert passed is True
    assert message == "Notebook matches key output checks."


def test_grade_notebook_outputs_fails_on_row_count(tmp_path: Path) -> None:
    key = tmp_path / "key.ipynb"
    student = tmp_path / "student.ipynb"

    _write_notebook(
        key,
        [
            {
                "cell_type": "code",
                "source": "answer",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[1, 2], [3, 4]]},
                    }
                ],
            }
        ],
    )
    _write_notebook(
        student,
        [
            {
                "cell_type": "code",
                "source": "answer",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[1, 2]]},
                    }
                ],
            }
        ],
    )

    passed, message = grade_notebook_outputs(key, student)
    assert passed is False
    assert "row count mismatch" in message


def test_grade_notebook_outputs_fails_fast_on_first_mismatch(tmp_path: Path) -> None:
    key = tmp_path / "key.ipynb"
    student = tmp_path / "student.ipynb"

    _write_notebook(
        key,
        [
            {
                "cell_type": "code",
                "source": "answer1",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[1, 2], [3, 4]]},
                    }
                ],
            },
            {
                "cell_type": "code",
                "source": "answer2",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[10, 20], [30, 40]]},
                    }
                ],
            },
        ],
    )
    _write_notebook(
        student,
        [
            {
                "cell_type": "code",
                "source": "answer1",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[9, 2], [3, 4]]},
                    }
                ],
            },
            {
                "cell_type": "code",
                "source": "answer2",
                "outputs": [
                    {
                        "output_type": "execute_result",
                        "data": {"application/json": [[0, 0], [0, 0]]},
                    }
                ],
            },
        ],
    )

    passed, message = grade_notebook_outputs(key, student)
    assert passed is False
    assert "Code cell 1, output 1" in message
    assert "first cell of first row mismatch" in message


def test_notebook_fixture_files_are_valid() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    key = fixtures / "key_simple.notebook.json"
    student_pass = fixtures / "student_simple_pass.notebook.json"
    student_fail = fixtures / "student_simple_fail_first_cell.notebook.json"

    for notebook in (key, student_pass, student_fail):
        data = json.loads(notebook.read_text())
        assert isinstance(data.get("cells"), list)
        assert len(data["cells"]) >= 1

        first_cell = data["cells"][0]
        assert first_cell.get("cell_type") == "code"
        assert first_cell.get("metadata", {}).get("language") == "python"
