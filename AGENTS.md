# AGENTS.md

## Commands

- Install (editable, with dev deps): `pip install -e ".[dev]"`
- Run all tests: `python -m pytest tests/ -v`
- Run a single test file: `python -m pytest tests/test_conflict.py -v`
- Run a single test: `python -m pytest tests/test_conflict.py::TestInstalledMismatch::test_installed_version_too_old -v`
- CLI entry point: `wheel-dedup install <wheels...>`

No linter, formatter, or typecheck is configured in this repo.

## Architecture

Single-package project. Source lives in `src/wheel_dedup/`, tests in `tests/`.

- `parser.py` — PEP 427 wheel filename parsing; `normalize()` does PEP 503 name normalization (`My_Package` → `my-package`). `WheelInfo` has both `path` (full) and `filename` (basename).
- `checker.py` — `InstalledChecker` wraps `importlib.metadata`, caches on first load. `get_all_installed()` returns `{normalized_name: version}` (no None values).
- `conflict.py` — Three conflict types: `installed_mismatch`, `inter_wheel`, `missing`. Conditional deps (lines with `;`) are ignored. Pending wheels that resolve an installed mismatch suppress the conflict.
- `installer.py` — Calls `pip install` via subprocess. Takes the **full path** to the wheel (not basename).
- `cli.py` — `argparse` with `install` subcommand. Flow: analyze → conflict check → confirm → install.

## Key Gotchas

- **Always use `info.path`** (not `info.filename`) when passing to `install_wheel()` — the filename is just the basename and won't resolve as a file path.
- **`WheelInfo.path` is the first field** in the dataclass; it was added after `filename`, so any code constructing `WheelInfo` must pass `path=` as a keyword or position it first.
- **`checker._cache` can contain `None`** values (packages with Name but no Version in metadata), but `get_all_installed()` filters them out. Don't read `_cache` directly.
- **`packaging` is the only third-party dependency** — used for `Requirement` and `Version` parsing in `conflict.py`. Don't add new deps without updating `pyproject.toml`.
- Build backend is **hatchling**, not setuptools. The package layout uses `src/` convention configured in `[tool.hatch.build.targets.wheel]`.

## CI

- Workflow: `.github/workflows/build.yml` — runs on every push and PR
- **test** job: 3 OS (ubuntu, macos, windows) × 6 Python (3.8–3.13), `fail-fast: false`
- **build** job: runs after all tests pass; produces a single `py3-none-any.whl` + sdist
- Integration tests in `test_integration.py` build real wheel ZIPs on disk (via `tmp_path`) — no mocking of `conflict.py` or `checker.py`
