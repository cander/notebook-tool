# notebook-tool

Python CLI utilities for tasks that compare two Jupyter notebooks.

## Setup

```bash
uv sync
```

## Commands

### Compare Markdown cells

Compares the Nth Markdown cell in notebook A to the Nth Markdown cell in notebook B.

- By default, whitespace differences are ignored.
- Use `--strict-whitespace` to treat whitespace as meaningful.

```bash
uv run notebook-tool compare-markdown path/to/first.ipynb path/to/second.ipynb
```

```bash
uv run notebook-tool compare-markdown path/to/first.ipynb path/to/second.ipynb --strict-whitespace
```

Exit codes:

- `0`: no differences found
- `1`: differences found
