# Forge Architecture

Forge is the autonomous software-engineering layer built on top of the original AI-Assistant repository.

```text
User Task
   |
   v
Task Contract
   |
   v
Planner (offline or OpenAI-backed)
   |
   v
+---------------- Tool Registry ----------------+
| repo_tree | read_file | write_file | git_*    |
| run_tests | future: patch, search, sandbox     |
+-----------------------------------------------+
   |
   v
Workspace Boundary
   |
   +--> Repository analysis
   +--> Controlled edits
   +--> Validation
   +--> Recovery loop (next milestone)
   |
   v
RunReport + structured step records
```

## Safety boundaries

The workspace resolves every requested path and rejects traversal outside the repository root. Commands use `subprocess.run(..., shell=False)`. OpenAI and GitHub credentials are removed from child-process environments.

Writes require an explicit approval flag. The default path is therefore read-only inspection and validation.

## Agent lifecycle

The production roadmap is: Planner → Repository Analyzer → Tool Selector → Executor → Test Runner → Debugger → Reviewer → Finalizer. The current implementation establishes the stable contracts for the planner, tools, workspace, execution records, and validation loop. Remaining production layers will extend these contracts rather than replace them.

## Model integration

The OpenAI-backed planner uses the Responses API through the official Python SDK. The OpenAI Agents SDK is a complementary option for richer orchestration, handoffs, guardrails, sessions, tracing, and sandbox agents; the current runtime keeps the core tool boundary independent so the provider can be swapped without changing repository safety primitives.
