# Project Instructions

A rule appears in this file only if (a) it encodes a project choice that cannot be inferred from the code, or (b) default model output violates it. Practices a model already follows unprompted, and anything ruff or ty enforces mechanically, are deliberately absent.

## 0. Project Overview

SHORT PROJECT DESCRIPTION

## 1. Python Environment

Use `uv` exclusively.

- Add dependencies: `uv add <package>` (dev: `uv add --dev <package>`)
- Sync environment: `uv sync`
- Run anything: `uv run <command>`, tests: `uv run pytest`

Do not use `pip`, `poetry`, `conda`, or `pip-tools` directly.

Format, lint, and type-check with:

```bash
uv run ruff format
uv run ruff check --fix
uv run ty check
```

## 2. Design Doctrine

<!-- BEGIN SYNCED DOCTRINE; source-sha256=59e37fd6b3dbab27530822e6956da51bb7ae76b637e3638530f99a8b4db9038d -->
Four rules. They are one design stance seen four ways: a module means one thing, receives exactly what it needs, in types that cannot lie, and dies rather than guess.

1. **A module means one thing.**
2. **It receives exactly what it needs.**
3. **Its types cannot lie.**
4. **It dies rather than guess.**
<!-- END SYNCED DOCTRINE -->

### 2.1 Denotation line

Before implementing a module, state in one line what it computes as a mathematical object, and record that line in the module docstring. Carriers must be named domain types, not placeholders.

```
preprocess : RawForcing × Attributes → Dataset   (pure)
training run = fold(update, θ₀, batches)
evaluation = map(metric) over (basin × model) pairs
```

If the line cannot be written, the design is not ready; say so instead of coding around it. In review, when the denotation line and the diff disagree, one of them is wrong.

### 2.2 Authority narrows

All wiring happens at the composition root: only the entry point (CLI command or `main()`) reads config files, reads environment variables, resolves paths, and opens stores. Every other module receives what it needs as arguments.

At every call, pass the narrowest argument that suffices: the two columns, not the DataFrame; the file path, not the directory; the three fields, not the config object. A function outside the entry module whose signature accepts the full config, or which constructs a `Path` from a literal, is a violation.

### 2.3 Parse, don't validate

Convert raw input (CLI args, YAML, NetCDF attributes) into domain types once, at the composition root. Downstream functions accept and return only domain types for concepts that carry an invariant or unit ambiguity: identifiers, physical quantities, config. A `float` that might be mm/day or m³/s must not exist past the boundary.

Enums over booleans: never `bool` for a domain state with two named possibilities. Use an `Enum` or `Literal["upstream", "downstream"]`, not `upstream: bool` — applies to parameters, fields, and return values.

Limits: domain types (`NewType`, frozen dataclass, enum) are for concepts with invariants, not for every value. Bulk numerical data stays in `xarray`/`polars` carriers; do not wrap arrays in classes.

### 2.4 Fail loud

Crash early on broken assumptions. No fallback values for required inputs (`.get(key, default)` on a required config key is a bug). No exception handler that logs and continues.

The one exception: a batch loop over independent items (e.g. per-basin processing) may have exactly one named isolation point that catches per-item failure, records which item failed and why, and continues. That point exists once per pipeline, not once per function.

## 3. Testing

### 3.1 Functional tests first

Prefer a small set of clear functional tests that exercise real behavior through public APIs, CLI commands, or complete workflows. Use real project implementations, temporary directories, and small representative input fixtures. Assert observable results: returned values, generated files, state changes, and meaningful failure cases.

- Test a user-visible behavior or a real regression. Avoid tests that merely mirror implementation steps, assert internal call counts, or check trivial forwarding and getters.
- Use focused unit tests for nontrivial isolated logic when they add confidence beyond the functional tests. Do not create a test for every helper or chase test-count and coverage targets.
- Mocks and stubs are exceptions for external boundaries that cannot reasonably run in a test, such as unavailable services, paid APIs, or nondeterministic third-party systems. Explain the reason in the test or fixture. Do not mock the project's own logic or patch internals to make a test pass.
- A passing test against a mocked container, database, or service does not establish that the real integration works. For changes to an integration, run a functional check against the real dependency when available. If it is unavailable, state what was not verified and why; never silently replace that verification with mocks.
- Keep fixtures and runtime small. Add cases for distinct behavior and important edge cases, and consolidate redundant tests rather than multiplying near-identical mock scenarios.

### 3.2 Complex data objects

Prefer library-specific assertions over manual element-wise checks of lengths, schemas, coordinates, shapes, or dtypes.

```python
np.testing.assert_allclose(result, expected)
xr.testing.assert_identical(result, expected)
pl_testing.assert_frame_equal(result_df, expected_df)
```
