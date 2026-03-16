from __future__ import annotations

import argparse
from pathlib import Path

from .compare import (
    compare_markdown_cells,
    grade_notebook_outputs,
    render_report_with_names,
    sync_markdown_cells,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notebook-tool",
        description="CLI utilities for working with pairs of Jupyter notebooks.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser(
        "compare-markdown",
        help="Compare corresponding Markdown cells in two notebooks.",
    )
    compare_parser.add_argument("first_notebook", type=Path, help="Path to first notebook")
    compare_parser.add_argument("second_notebook", type=Path, help="Path to second notebook")
    compare_parser.add_argument(
        "--strict-whitespace",
        action="store_true",
        help="Treat whitespace differences as meaningful.",
    )

    sync_parser = subparsers.add_parser(
        "sync-markdown",
        help="Interactively synchronize Markdown cells between two notebooks.",
    )
    sync_parser.add_argument("first_notebook", type=Path, help="Path to first notebook")
    sync_parser.add_argument("second_notebook", type=Path, help="Path to second notebook")
    sync_parser.add_argument(
        "--strict-whitespace",
        action="store_true",
        help="Treat whitespace differences as meaningful.",
    )

    grade_parser = subparsers.add_parser(
        "grade-notebook",
        help="Grade code cell outputs in a notebook against a key notebook.",
    )
    grade_parser.add_argument("key_notebook", type=Path, help="Path to key notebook")
    grade_parser.add_argument("notebook_to_grade", type=Path, help="Path to notebook to grade")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "compare-markdown":
        try:
            differences = compare_markdown_cells(
                args.first_notebook,
                args.second_notebook,
                ignore_whitespace=not args.strict_whitespace,
            )
        except ValueError as exc:
            parser.exit(status=2, message=f"Error: {exc}\n")
        report = render_report_with_names(
            differences,
            args.first_notebook,
            args.second_notebook,
        )
        print(report)
        raise SystemExit(1 if differences else 0)

    if args.command == "sync-markdown":
        try:
            sync_markdown_cells(
                args.first_notebook,
                args.second_notebook,
                ignore_whitespace=not args.strict_whitespace,
            )
        except ValueError as exc:
            parser.exit(status=2, message=f"Error: {exc}\n")
        return

    if args.command == "grade-notebook":
        try:
            passed, message = grade_notebook_outputs(
                args.key_notebook,
                args.notebook_to_grade,
            )
        except ValueError as exc:
            parser.exit(status=2, message=f"Error: {exc}\n")
        print(message)
        raise SystemExit(0 if passed else 1)

    parser.error(f"Unknown command: {args.command}")
