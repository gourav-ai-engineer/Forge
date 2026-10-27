# Forge operator runbook

## 1. Safe offline verification

```bash
python -m pip install -e ".[dev]"
python forge_cli.py "Inspect this repository and run its tests" --repo . --json
```

This uses the deterministic planner and never needs an API key.

## 2. Model-backed planning

Install the optional provider:

```bash
python -m pip install -e ".[openai,dev]"
```

Set `OPENAI_API_KEY` in the process environment. Never place the key in repository files, command history committed to source, or `.env` tracked by Git.

Run:

```bash
python forge_cli.py "Inspect this repository, diagnose the failing test, and propose a minimal fix" --repo ./sample-repo --json
```

For mutations, explicitly add `--allow-writes` after reviewing the task and workspace.

## 3. Local HTTP inspection API

```bash
python forge_cli.py --serve --repo . --port 8787
```

The service exposes read-only run inspection endpoints. Mutating operations remain in the CLI/tool runtime and require the write gate.

## 4. Docker

```bash
docker compose up --build
```

The container is intended for local/self-hosted evaluation. Production deployment needs a hosting target with a managed container runtime and secret store.

## 5. Verification checklist

Before calling a Forge change complete:

- `pytest -q` passes.
- `ruff check forge tests forge_cli.py` passes.
- Offline Forge smoke test passes.
- Existing assistant smoke test passes.
- No credentials or generated runtime state are tracked.
- Final diff is reviewed.
- A model-backed run is recorded separately from deterministic CI verification when an API key is available.
