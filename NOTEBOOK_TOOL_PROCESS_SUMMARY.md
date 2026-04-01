# Notebook Tool Process Summary (Agent-Plan Style)

## Objective
Create a CLI that helps reconcile and evaluate paired Jupyter notebooks used in teaching workflows, with a focus on:

- Comparing and syncing Markdown prompt cells between assignment and key notebooks
- Grading student notebook outputs against a key notebook using practical, fail-fast checks

## Plan Snapshot

Status key: `[x]` complete, `[ ]` pending

- [x] Define core problem and scope
- [x] Build notebook parsing + Markdown comparison
- [x] Add interactive Markdown sync workflow
- [x] Add output grading for code cells
- [x] Expose functionality through a CLI
- [x] Add tests for behavior and regressions
- [x] Document usage and exit-code behavior
- [ ] Extend grading beyond current tabular checks

## Execution Log

### Phase 1: Problem Framing and Constraints
- Captured the real teaching pain point: assignment and key notebooks drift when Markdown is updated in only one copy.
- Chose to treat Markdown as the authoritative assignment content.
- Set explicit scope to compare corresponding Markdown cells by position.

### Phase 2: Core Comparison Engine
- Implemented notebook JSON loading and validation (`cells` must exist and be list-like).
- Extracted Markdown cells only, ignoring code cells for this workflow.
- Added normalization mode that collapses whitespace for tolerant comparison.
- Added strict mode to preserve exact whitespace matching when needed.

### Phase 3: Report Rendering and UX
- Added readable diff rendering with clear first/second file labeling.
- Introduced colorized output for visual scanning in terminal sessions.
- Standardized comparison output into a concise per-cell difference report.

### Phase 4: Interactive Synchronization
- Built `sync-markdown` flow to walk mismatched Markdown cells in order.
- Added per-cell actions: copy first -> second, copy second -> first, skip, quit.
- Wrote updates back to notebook JSON with predictable formatting.
- Tracked notebook modifications so saves only happen when needed.

### Phase 5: Notebook Output Grading
- Added `grade-notebook` command using key notebook as source of truth.
- Restricted grading to tabular outputs and ignored non-tabular render artifacts.
- Supported multiple payload styles (`application/json`, dataresource JSON, text fallback parsing).
- Implemented fail-fast checks in fixed order:
  1. row count
  2. column count
  3. first cell of first row
  4. last cell of first row
  5. first cell of last row
  6. last cell of last row
- Returned informative first-failure messages for fast diagnosis.

### Phase 6: CLI Integration
- Added a single CLI entrypoint with subcommands:
  - `compare-markdown`
  - `sync-markdown`
  - `grade-notebook`
- Added argument parsing for notebook paths and `--strict-whitespace` toggle.
- Standardized exit-code semantics:
  - compare: `0` no differences, `1` differences
  - grade: `0` pass, `1` fail
  - invalid notebook/value errors: parser exits with status `2`

### Phase 7: Test Coverage and Fixtures
- Added tests for whitespace-tolerant comparison and exact-difference reporting.
- Added tests for sync decisions (copy both directions, skip, quit).
- Added tests for grading pass, row mismatch failure, and fail-fast behavior.
- Added tests confirming non-tabular outputs are ignored.
- Added fixture validation ensuring test notebook JSON files are structurally valid.

### Phase 8: Packaging and Documentation
- Configured project metadata and script entrypoint in `pyproject.toml`.
- Added pytest dev dependency for local test runs.
- Documented commands, options, and exit codes in README.

## Key Decisions and Tradeoffs

- Positional matching for Markdown cells was chosen for simplicity and predictability.
- Whitespace-insensitive comparison is default to reduce noise from formatting-only edits.
- Grading uses lightweight representative checks rather than full-table deep equality for speed and robustness.
- Fail-fast grading was chosen to give immediate actionable feedback.

## Current State

- CLI supports compare, sync, and grade workflows end-to-end.
- Core behavior is covered by tests, including fixture validity checks.
- Documentation reflects command usage and expected outcomes.

## Next Steps

- Implement richer grading for additional output patterns and edge cases.
- Consider configurable grading policies (strictness levels/check toggles).
- Add summary reporting mode that aggregates all mismatches (non-fail-fast mode).
- Expand fixtures to include larger multi-cell notebooks and mixed output scenarios.
