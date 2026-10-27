# Forge PRD Alignment

This document distinguishes implemented functionality from roadmap work so feature and resume claims remain verifiable.

## Implemented now

| Capability | Implementation and boundary |
|---|---|
| Bounded autonomous loop | ForgeEngine limits rounds and steps and records every tool result |
| Repository understanding | Language/profile summary, file tree, Git status and diff |
| Typed tool use | Explicit tool names and structured arguments; no general-purpose shell tool |
| Workspace security | Path traversal and symlink rejection, protected secret paths, ignored runtime directories |
| Approval-gated mutation | File writes and commits require explicit authorization; commits require explicit file paths |
| Code RAG | Line-aware chunks, offline BM25 retrieval, optional Chroma vector retrieval with reciprocal-rank fusion |
| Model-backed planning | Optional OpenAI Responses API provider; offline planner remains available |
| Validation | pytest, npm, and Go test-runner detection; host test execution skipped by default |
| Sandboxed validation | Disposable Docker container, network disabled, limited privileges/resources, read-only checkout mount, tests run on a temporary copy |
| Persistent run evidence | JSON reports under .forge/runs |
| GitHub issue intake | Public issue URL parsing and title/body retrieval; user supplies a matching local checkout |
| Guarded pull requests | Creates a branch and unmerged PR through GitHub API only after successful sandboxed validation |
| Read-only service API | FastAPI health and run endpoints; optional API key and allowed workspace root |
| CI and evaluation harness | Unit tests, static lint, offline smoke test, deterministic repair fixture, and runtime safety checks |
| Safe browser demo | Fixed deterministic trace; no arbitrary visitor code or repository changes are executed |

## Important sandbox limitations

The configured example image is suitable for Forge's own Python test suite. Other projects may need a custom image with their test dependencies preinstalled. Forge does not build untrusted repository Dockerfiles on the host. The current controls reduce risk but are not equivalent to a hardened multi-tenant virtual machine; gVisor/Firecracker, seccomp/AppArmor profiles, stronger tenant isolation, and resource accounting remain future work.

The Docker test container has network disabled and reads the host checkout through a read-only bind mount. Its temporary copy is used for test execution so test-side writes do not alter the checkout through that mount.

## Remaining milestones

### Code intelligence
- AST/tree-sitter symbol index
- test-to-source mapping
- smarter retrieval evaluation and reranking
- curated retrieval relevance dataset

### Evidence and evaluation
- event stream beyond JSON run reports
- structured before/after patch artifacts
- failure classification and patch-risk scoring
- curated bug-fix evaluation set, hidden regression tests, success/iteration/cost/latency reporting
- model and policy comparisons with reproducible evidence

### Security and operations
- stronger OS-level isolation and seccomp/AppArmor profiles
- pinned dependency images and custom repository test environments
- rate limits, quotas and artifact retention for multi-tenant service deployment
- deeper API integration tests and production deployment monitoring

## Engineering principles

1. Verification over generation: generated code is not success until validation passes.
2. Least privilege: read-only is the default; mutations are explicitly authorized.
3. Untrusted repository: source code and tool output are data, not trusted instructions.
4. Bounded autonomy: every planner loop has step and round limits.
5. Reproducibility: keep benchmark fixtures deterministic and retain raw results.
6. Honest measurement: no SWE-bench or model-quality scores are claimed without running a defined evaluation.
7. Human review: Forge opens pull requests only when explicitly requested and never auto-merges.
