# Forge — Autonomous AI Software Engineer

Forge is a verification-first coding-agent runtime for inspecting repositories, retrieving relevant code, planning bounded tool calls, proposing changes, and checking those changes before delivery. It combines the autonomous engineering workflow from the Forge resume project with the repository-level bug-analysis and code-RAG features from the AI GitHub Engineer project.

Forge is a learning and portfolio reference implementation. The offline inspection path works without an API key. Model-backed planning, Chroma retrieval, sandbox execution, and GitHub pull-request publishing are optional integrations.

## What it does

- **Repository understanding:** inventories supported source files, profiles the repository, checks Git state, and exposes bounded file/search tools.
- **Code retrieval (RAG):** chunks source code with line metadata and ranks relevant snippets with BM25. An optional ChromaDB backend adds vector retrieval and reciprocal-rank fusion.
- **LLM planning:** an optional OpenAI Responses API planner produces structured calls into a typed tool registry; the model does not get a general-purpose shell tool.
- **Bounded execution:** limits steps and recovery rounds, stores JSON run reports under the ignored .forge/runs directory, and reviews diffs after edits.
- **Explicit write approval:** file writes and Git commits are disabled by default. Commits must name their intended paths.
- **Sandbox validation:** tests can run in a disposable Docker container with no network, dropped Linux capabilities, no-new-privileges, a read-only container root, CPU/memory/PID limits, and a read-only mount of the source checkout. The container tests a temporary copy.
- **GitHub issue intake:** the --issue flag fetches a public issue and turns its title/body into the task prompt.
- **Guarded pull requests:** optionally creates a new branch and unmerged PR via the GitHub API only when the Forge run succeeds and its final test validation passed in the Docker sandbox.
- **Read-only HTTP API:** FastAPI health and run endpoints, with optional API-key authentication and workspace-root enforcement.
- **Evaluation:** unit tests, a deterministic repair-loop benchmark, and runtime safety checks. Benchmarks are not claims of SWE-bench-level issue-resolution performance.

## Architecture

    Task / GitHub Issue
             |
             v
    Repository profile + file tree
             |
             v
    Code retrieval: BM25 (optional Chroma hybrid)
             |
             v
    OpenAI planner -> typed tool registry
             |
             v
    inspect -> read/search -> propose minimal edit
             |
             v
    diff review -> Docker sandbox test -> bounded recovery
             |
             v
    JSON run report -> optional GitHub pull request

The normal HTTP API is read-only. Mutating work belongs to the CLI and requires explicit flags.

## Requirements

- Python 3.11 or newer (Python 3.12 is the CI target)
- Git for repository status/diff/commit support
- Docker Desktop or Docker Engine to use isolated validation
- An OpenAI API key only for model-backed planning
- A GitHub token only for creating pull requests; issue fetching works with public issues without a token

## Install on Windows PowerShell

    git clone https://github.com/gourav-ai-engineer/Forge.git
    cd Forge
    py -3.12 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev,openai]"
    Copy-Item .env.example .env

Edit .env and set OPENAI_API_KEY to enable model-backed planning. The default model is gpt-4o-mini and can be changed with FORGE_MODEL. Do not commit .env or paste credentials into issue text.

On macOS/Linux, replace the virtual-environment activation command with:

    source .venv/bin/activate

## First run: offline inspection

    python forge_cli.py "Inspect this repository and summarize its structure" --repo . --json

The offline planner inventories the repository, records Git state, and produces a persistent report. Test execution is deliberately skipped unless Docker sandboxing is enabled or the unsafe local-test opt-in is explicitly set.

## Run with the LLM planner

    python forge_cli.py "Find likely causes of the failing test and explain a minimal repair plan" --repo ../sample-project --json

The model-backed path requires OPENAI_API_KEY. Without it, Forge uses the deterministic offline inspection planner.

## Search relevant code with RAG

Code retrieval is available to the planner as the search_code tool. BM25 is the default backend and works offline.

For optional ChromaDB-backed vector retrieval:

    python -m pip install -e ".[vector]"
    # Set FORGE_USE_CHROMA=1 in .env
    python forge_cli.py "Find where authentication errors are handled" --repo ../sample-project --json

The first vector-index build may download Chroma's default embedding model. With FORGE_USE_CHROMA unset or set to 0, retrieval remains lexical and offline. Relevance must be evaluated on a representative task set before quoting an accuracy improvement.

## Enable the Docker sandbox

Build Forge's example validation image from the repository root:

    docker build -f Dockerfile.sandbox -t forge-sandbox:local .

Then run an authorized task against a local checkout:

    python forge_cli.py "Fix the failing unit test with the smallest safe change" --repo ../sample-project --allow-writes --sandbox --max-steps 24 --json

The sandbox image includes Forge's core dependencies and test tooling. For another project's custom dependencies, build a purpose-built sandbox image containing those dependencies and set FORGE_SANDBOX_IMAGE accordingly. The sandbox copies the target repository to a temporary container filesystem and leaves the mounted source read-only.

Forge intentionally does not execute arbitrary repository tests on the host by default. FORGE_ALLOW_UNSANDBOXED_TESTS=1 is an unsafe opt-in intended only for trusted, self-generated fixtures such as the deterministic benchmark.

## GitHub issue to pull request

Clone the repository locally first and make sure its working tree is clean. Set GITHUB_TOKEN in .env with repository content-write and pull-request permissions. Build the sandbox image as described above.

    python forge_cli.py --issue https://github.com/OWNER/REPOSITORY/issues/123 --repo ../REPOSITORY --allow-writes --sandbox --create-pr --json

Optional flags include --pr-title "Fix: concise description", --pr-base release-branch, and --max-steps 24.

The command requires the local HEAD commit to exist on GitHub, a clean working tree before the Forge run, no protected-file changes, and successful final sandboxed tests. It creates a reviewable branch and pull request; it never merges automatically. The API token is sent only to api.github.com and is not passed to child processes or logged by Forge.

Supported GitHub remote formats are HTTPS and SSH origins on github.com. The CLI refuses PR creation when validation did not complete successfully or when the repository has pre-existing local changes.

## Start the read-only API

    python forge_cli.py --serve --repo . --host 127.0.0.1 --port 8787

Health check: http://127.0.0.1:8787/health  
Interactive API docs: http://127.0.0.1:8787/docs

POST JSON to /run or /api/v1/tasks:

    {
      "request": "Inspect the repository and identify its test entry points"
    }

When FORGE_API_KEY is set, include the X-API-Key header. Binding to a non-local host requires FORGE_API_KEY. Set FORGE_ALLOWED_ROOT to restrict which configured workspace path the API may inspect. The HTTP surface never enables file writes or Git commits.

## Docker Compose API

Copy .env.example to .env, set a non-empty FORGE_API_KEY, optionally set OPENAI_API_KEY for model-backed planning, and create a local repository folder containing the checkout you want to inspect. Without OPENAI_API_KEY, the service uses the offline planner. Then run:

    docker compose up --build

The API is mapped to port 8787. Compose binds the mounted workspace to ./repository; it does not mount your entire home directory. For testing, use a dedicated checkout rather than a directory containing secrets.

## Tests, lint, and benchmarks

    python -m pip install -e ".[dev]"
    pytest -q
    ruff check forge tests benchmarks forge_cli.py
    python forge_cli.py "Inspect this repository" --repo . --json
    python benchmarks/run_benchmark.py --json
    python benchmarks/agentic_recovery_benchmark.py --json

The deterministic repair benchmark uses a small generated calculator fixture to test the inspect-edit-diff-test recovery path without an LLM. It explicitly enables host test execution only for that trusted fixture. This benchmark tests runtime behavior, not the general correctness of LLM-generated patches.

## Safety design

- The planner can call typed tools; there is no free-form shell-command tool.
- Reads and writes are constrained to the configured workspace, reject path traversal and symlinks, and protect common credential paths.
- File writes and commits require explicit authorization; writes under .github automation paths are blocked.
- Child process environments are allowlisted so API tokens and unrelated host secrets are not inherited.
- Repository tests are skipped unless sandboxed or an explicit trusted-local opt-in is configured.
- Sandboxed validation has no network and tests an ephemeral copy of the source tree.
- Pull requests require a clean pre-run checkout and successful sandbox validation; Forge never auto-merges.
- Run reports and vector indexes are stored under .forge/, which is excluded from repository indexing and Git.

These controls reduce risk but do not make arbitrary code safe. Use Forge only on repositories you are authorized to inspect. Review every generated diff and PR. A container is not a substitute for stronger isolation such as gVisor or Firecracker for high-risk multi-tenant execution.

## Interview preparation

Read docs/ARCHITECTURE.md, docs/INTERVIEW_GUIDE.md, and docs/OPERATOR_RUNBOOK.md for the runtime data flow, deep-dive questions, and practical operating guidance. Start by understanding the boundaries between the planner, retrieval, tool registry, workspace, validator, report store, and GitHub publisher.

## Project status and honest claims

Forge implements a bounded agent runtime with explicit tool authorization, offline code retrieval, optional vector search, optional model-backed planning, sandbox validation, and optional guarded GitHub PR creation. Re-run tests and benchmarks on your machine before reporting results. Do not claim an issue-resolution rate, a 3x speedup, or production-grade multi-tenant isolation unless measured on a defined evaluation set and environment.
