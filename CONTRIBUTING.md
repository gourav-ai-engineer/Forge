# Contributing to Forge

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check forge tests forge_cli.py
```

Keep changes focused and add tests for new behavior. Do not commit secrets, local `.env` files, generated run state, IDE metadata, or Python bytecode.

## Architecture rule

New capabilities should pass through typed interfaces and the `ToolRegistry` rather than invoking arbitrary shell commands. Any operation that can mutate the workspace must remain behind an explicit write/approval boundary.

## Pull requests

Describe the problem, design change, security impact, and verification performed. Include example CLI output when behavior changes are user-facing.
