# Forge Interview Guide

## Explain the system in 30 seconds
Forge is a repository-scoped autonomous software-engineering runtime. A task enters a structured contract, the agent first profiles the repository and establishes a test baseline, then a model planner can issue typed tool calls for inspection and edits. Each action is recorded with timing and success state; a final diff/test pass provides a validation boundary. Writes and commits are approval-gated.

## Why typed tools instead of shell text?
A model can be prompted to emit a shell command, but that creates a larger injection and parsing surface. Forge accepts a tool name plus structured arguments, validates paths at the workspace boundary, and executes subprocesses without a shell.

## How does recovery work?
The runtime feeds previous tool results back into the planner for a bounded number of rounds. Test failures therefore become context for a new repair plan instead of terminating the workflow immediately.

## How is the workspace isolated?
The current core enforces filesystem boundaries and strips credentials from child processes. The Docker profile adds a non-privileged container boundary. A production deployment should additionally enforce CPU/memory quotas and network egress policy.

## What is deterministic?
The offline planner is deterministic and needs no external API. That makes CI and demos reproducible. The OpenAI planner is an optional provider for real autonomous planning.

## What would you improve next?
Add patch-native edits, semantic code search, a persistent event stream, model/agent handoffs, richer reviewer agents, container snapshots, resource quotas, network policy, GitHub pull-request integration, and an evaluation suite with task success rate, test repair rate, step efficiency, and cost/latency metrics.
