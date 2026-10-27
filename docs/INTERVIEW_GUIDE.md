# Forge Interview Guide

## Explain the system in 30 seconds

Forge is a repository-scoped autonomous software-engineering runtime. It profiles a codebase, retrieves relevant snippets using BM25 or optional Chroma vector search, and gives an LLM a bounded set of typed tools. The agent can inspect code and, only when explicitly authorized, propose changes. Forge reviews the diff, validates the result in an isolated Docker copy, recovers from test failures within a bounded budget, and persists a structured report. A separate gated workflow can open a GitHub pull request after successful sandboxed validation; Forge never auto-merges.

## Why typed tools instead of shell text?

A model that emits arbitrary shell commands creates a wider parsing and command-injection surface. Forge accepts a tool name plus structured arguments, validates paths at the workspace boundary, and launches subprocesses without a shell. The trade-off is that new actions must be implemented as explicit tools rather than being available automatically.

## Why use RAG on a code repository?

A large repository often exceeds an LLM's context window. Code retrieval narrows context to relevant files and line ranges. BM25 is the offline baseline; optional Chroma retrieval adds semantic search and the two rankings are combined with reciprocal-rank fusion. Retrieval relevance should be evaluated separately from final patch correctness.

## How does the recovery loop work?

The engine feeds previous tool results and errors into the planner on the next bounded round. A failed test becomes evidence for a repair attempt rather than a success claim. The final status requires a successful final validation; a skipped validation is not treated as a passed test.

## How is the workspace isolated?

Path handling rejects traversal and symlinks and blocks common secret paths. Child processes receive an allowlisted environment, so OpenAI/GitHub tokens are not inherited. The Docker runner mounts the checkout read-only and executes tests on a temporary copy with network disabled and resource limits. A container lowers risk but is not a substitute for gVisor/Firecracker in high-risk multi-tenant environments.

## How does guarded PR publishing work?

The CLI requires writes and sandbox flags, a clean initial working tree, a recorded starting HEAD, a GitHub token, and a successful final sandbox test. Forge constructs a commit through GitHub's Git Data API and opens a PR against the selected/default base branch. It blocks protected files and deletes/renames. The PR is always left unmerged for a human reviewer.

## What is deterministic?

The offline planner and benchmark fixtures are deterministic. The OpenAI provider is optional and its output depends on the model, prompt, context, and runtime. The deterministic recovery benchmark tests the engine/tool/recovery path, not the general correctness of LLM-generated changes.

## What would you improve next?

Add AST-aware retrieval, code-symbol and test-to-source indexes, a larger curated bug-fix evaluation set, structured patch artifacts, stronger sandbox isolation, clearer token/cost telemetry, and a background job queue for long-running tasks. The next claims should be grounded in measured task-success and regression rates.
