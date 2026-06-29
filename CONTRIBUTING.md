# Contributing

## Setup

```bash
uv sync --extra dev
```

## Test

```bash
uv run pytest
```

## Branching & commits

- Branch naming: `feat/<slug>`, `fix/<slug>`, `chore/<topic>`.
- Commit style: [Conventional Commits](https://www.conventionalcommits.org),
  imperative mood, one logical change per commit.

## Submitting changes

1. Branch off `main`.
2. Make your change and ensure `uv run pytest` passes locally.
3. Open a PR. CI must be green before review.
4. Keep each PR scoped to one logical change.
