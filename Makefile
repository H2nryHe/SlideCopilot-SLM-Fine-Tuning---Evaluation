.PHONY: install test lint help

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	python -m compileall src

help:
	pptcopilot --help
