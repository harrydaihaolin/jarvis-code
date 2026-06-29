# Agent guide

Jarvis Code is a personal AI coding assistant CLI powered by Claude. The
package lives in `jarvis/`; the entry point is `jarvis.main:run` (exposed as the
`jarvis` console script).

## Quick start

```bash
# Install dependencies (uv reads pyproject.toml + uv.lock)
uv sync --extra dev

# Run tests
uv run pytest

# Run the CLI
uv run jarvis
```

If you don't use `uv`, the pip-based equivalents work too:

```bash
pip install -e ".[dev]"
pytest
jarvis
```

`ANTHROPIC_API_KEY` must be set in the environment before running the CLI.

## Do-not-touch

- `uv.lock` — regenerate with `uv lock`, never hand-edit.
- `.venv/`, `dist/`, `build/`, `*.egg-info/` — generated artefacts.

## Conventions

- Branch naming: `feat/<short>`, `fix/<issue>`, `chore/<topic>`.
- Commit style: Conventional Commits, one logical change per commit.
- PR scope: one logical change per PR.

## CI and the feedback loop

**CI is part of the feedback loop.** After you push or update a PR, monitor the
GitHub Actions run. When CI fails, read the logs, fix the root cause, and push
follow-up commits. Do not stop while checks are red.
