# Contributing to OMirror

Thanks for taking the time to contribute! Here is everything you need to get started.

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) — install via `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Setup

```bash
git clone https://github.com/omar-hindawi98/omirror.git
cd omirror
uv sync

# Install pre-commit hooks (commitizen + ruff)
uvx pre-commit install --hook-type commit-msg --hook-type pre-commit
```

On a Raspberry Pi, also install the hardware extras:

```bash
uv sync --extra pi
```

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/) enforced by commitizen.

```
<type>(<scope>): <short description>

feat(bluetooth): add RGB flash sequence characteristic
fix(weather): handle missing API key gracefully
chore(deps): bump feedparser to 6.0.11
docs: update installation instructions
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

The pre-commit hook will reject non-conforming messages automatically. You can also use `cz commit` as an interactive prompt.

## Running tests

The test suite runs on any machine (no Pi hardware required):

```bash
uv run pytest tests/ -v
```

Tests are in `tests/` and cover data modules, BLE protocol logic, display helpers, and time utilities. Pi-only imports (`lgpio`, `pigpio`, `dbus`) are stubbed automatically inside the relevant test files.

When adding a new feature, add matching tests. When fixing a bug, add a regression test that would have caught it.

## Code style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Run the checks before every commit:

```bash
uvx ruff check src/        # lint
uvx ruff format src/       # format in-place
uvx ruff format --check src/   # check only (CI mode)
```

Rules are in `pyproject.toml` under `[tool.ruff]`. The short version:

- Double quotes, 4-space indent, 100-character line limit
- Imports sorted (isort-style, first-party = `omirror`)
- No unused imports, no shadowed builtins, prefer f-strings

## Conventions

- **English only** — all identifiers, comments, commit messages, and user-facing strings
- **No magic paths** — use constants from `omirror.const` (`IMAGES_DIR`, `FONTS_DIR`, etc.)
- **No secrets** — never commit API keys; keep real values in `settings.json` which is gitignored-safe as a personal config
- **One concern per file** — widget display logic lives in `display/widgets/`, data-fetching in `widgets/`, hardware drivers in `hardware/`
- **No comments for the obvious** — only add a comment when the *why* is non-obvious

## Submitting a PR

1. Fork the repo and create a branch from `main`
2. Make your changes and run the linter
3. Open a pull request — the PR template will guide you through the checklist
4. CI will validate lint, format, tests, and commit messages automatically

## Reporting bugs

Open an issue with:

- What you expected to happen
- What actually happened (with any tracebacks)
- Your Pi model and OS version
- Relevant section of `settings.json` (redact your API key)
