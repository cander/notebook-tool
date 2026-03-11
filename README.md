# notebook-tool

A CLI utility for tasks that work with pairs of Jupyter notebooks.

I have a pattern in a class I teach where I assign a Jupyter notebook via
GitHub Classroom that students complete and submit. Then, I have the "key"
notebook which is a copy of the assignment with the solution included. The
rub is while I'm grading, I often see issues with the questions (typos,
things that could be clarified, etc.), and so I change the relevant Markdown
cells. Then problem is that I often make the change in one notebook but not
the other. This tool aims to help facilitate reconciling the notebooks.

Note that because the original assignment is the Markdown cells, I'm only
concerned with differences in those cells.

## To Do

- sync cells between notebooks
- grade code cells

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
