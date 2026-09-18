# Root Makefile for DreamLayer project using Poetry and pre-commit

# Run the application entry point
run:
	poetry run python dreamlayer/dream_layer.py

# Run tests quietly with pytest
test:
	poetry run pytest -q

# Run all pre-commit hooks (linting, formatting checks, etc.)
lint:
	poetry run pre-commit run --all-files

# Combined step for CI pipelines
ci:
	make lint && make test
