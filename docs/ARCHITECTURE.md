# Forge Architecture

Forge is a repository-scoped autonomous software-engineering runtime. Its main path is:

    Developer task or GitHub issue URL
                  |
                  v
        Task contract + budget
                  |
                  v
        Repository profile + tree
                  |
                  v
      BM25 code retrieval (default)
       optional Chroma vector search
                  |
                  v
       OpenAI / offline planner
                  |
                  v
         Typed tool registry
          /      |       \
     inspect   propose   validate
       code      edits      |
          \      |       /
             Git diff
                 |
                 v
       Docker sandbox validation
                 |
       failure -> bounded recovery
                 |
                 v
       Persistent RunReport JSON
                 |
        optional guarded GitHub PR

## Main components

- **ForgeEngine:** coordinates the baseline inspection, bounded plan/execute rounds, recovery, final validation, and report persistence.
- **Planner:** deterministic OfflinePlanner for no-key smoke tests, or OpenAIPlanner using the Responses API. Model output is parsed into ToolCall records.
- **ToolRegistry:** exposes named operations such as repository analysis, file-tree listing, bounded reads, substring search, BM25/optional Chroma code retrieval, file writes, Git status/diff/commit, and test validation.
- **Workspace:** resolves paths inside one repository, rejects traversal and symlinks, protects common secret/config paths, and runs subprocesses without a shell using an allowlisted environment.
- **CodeRetriever:** chunks eligible source files with line metadata; BM25 is offline by default. When FORGE_USE_CHROMA=1 and the optional dependency works, lexical and vector rankings are combined with reciprocal-rank fusion.
- **SandboxRunner:** mounts the user's checkout read-only, copies it into a temporary container filesystem, disables network access, drops Linux capabilities, enables no-new-privileges, makes the container root read-only, and applies CPU/memory/PID/time limits.
- **RunStore:** writes structured run reports under .forge/runs; this state is excluded from source indexing and Git.
- **GitHub integration:** fetches issue text from public issue URLs. An explicit CLI option can create an unmerged pull request through the GitHub Git Data and Pull Requests APIs after successful sandbox validation.
- **FastAPI service:** exposes health and read-only run endpoints. It accepts a task request, not an arbitrary repo path; optional API-key authentication and a configured workspace-root policy are supported.

## Safety boundaries

The model receives typed tool definitions described by a system prompt; it does not receive an unrestricted shell tool. File writes and Git commits require an explicit CLI authorization flag, and commits require an explicit list of paths. Writes under GitHub automation configuration paths are blocked. Common secret files and credential directories are blocked from workspace reads and indexing. Child processes receive only an allowlisted environment, preventing OpenAI and GitHub tokens from being inherited.

Test execution is skipped by default when no Docker sandbox has been configured. The unsafe local-test opt-in exists only for trusted fixtures. The sandbox's repository bind mount is read-only; tests run against a temporary copy inside the disposable container. PR creation is gated on a successful report and a final successful sandbox test step; the PR is never merged automatically.

## Failure handling

Each action becomes a step record with a tool name, success flag, captured output, and elapsed time. Tool failures and test failures become planner context on later bounded rounds. Forge does not treat an LLM-generated patch as successful merely because the patch was written; it requires a successful final validation step to mark a mutation run successful.

## Implemented vs. future work

The current code includes repository profiling, BM25/optional Chroma code retrieval, tool-driven planning, bounded recovery, JSON reports, a read-only FastAPI API, Docker validation, issue intake, guarded PR publishing, tests, lint, CI, and deterministic benchmarks.

Future hardening could add AST/tree-sitter symbol maps, test-to-source mapping, stronger OS-level sandboxing (gVisor/Firecracker), artifact quotas, richer event telemetry, and evaluation on a curated public bug-fix benchmark. No general model issue-resolution rate is claimed without that evaluation.
