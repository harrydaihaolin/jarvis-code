.PHONY: help install test run lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "%-20s %s\n", $$1, $$2}'

install: ## Install dependencies (incl. dev extras)
	uv sync --extra dev

test: ## Run the test suite
	uv run pytest

run: ## Run the Jarvis CLI
	uv run jarvis

lint: ## Lint the codebase
	uv run ruff check .
