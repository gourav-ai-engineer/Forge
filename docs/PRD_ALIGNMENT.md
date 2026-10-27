# Forge PRD Alignment

This document maps the **Autonomous Coding Agent & Secure Evaluation Sandbox** PRD to the current implementation. It is intentionally explicit about what is implemented versus what remains roadmap work, so project and resume claims stay defensible.

## Implemented now

| PRD capability | Forge implementation |
|---|---|
| Bounded autonomous loop | `ForgeEngine` with configurable rounds and step budget |
| Repository understanding | repository tree + repository profile analysis |
| Typed agent tools | `ToolRegistry` with explicit read/write tool sets |
| Safe code access | workspace-relative path resolution and traversal protection |
| Approval-gated mutation | `write_file` and `git_commit` require authorization |
| Validation | pytest / npm / Go test detection |
| Failure-aware recovery | bounded planner rounds and final validation |
| Persistent execution state | JSON reports under `.forge/runs` |
| Model-backed planning | optional OpenAI Responses API provider |
| Safety benchmark | deterministic checks for write/commit/path/credential boundaries |
| Recovery benchmark | deterministic broken-fixture repair and final-test validation |
| Sandboxed validation | hardened Docker runner for explicitly authorized mutation runs |
| Safe portfolio demo | deterministic browser walkthrough; no arbitrary visitor execution |

## Sandbox controls implemented

The Docker runner is intentionally conservative:

- network disabled with `--network=none`
- all Linux capabilities dropped
- `no-new-privileges`
- read-only container root filesystem
- bounded PID count
- bounded memory
- bounded CPU
- ephemeral `--rm` container
- temporary `tmpfs` for `/tmp`
- controlled repository mount
- no shell wrapping of the requested command

The sandbox image is configurable with `FORGE_SANDBOX_IMAGE`.

### Important limitation

A generic sandbox image cannot automatically contain every repository's dependency graph. Production deployments should use purpose-built, pinned images with dependencies prepared ahead of time. Building an untrusted repository's Dockerfile on the host is **not** considered a safe sandbox strategy.

## Next milestones

### Phase 1 — Issue intake

- GitHub issue URL/number parsing
- repository/commit pinning
- normalized task object
- read-only GitHub metadata client

### Phase 2 — Code intelligence

- tree-sitter parsing
- symbol index
- AST-aware search
- test-to-source mapping
- BM25/embedding retrieval

### Phase 3 — Evidence and review

- structured trajectory events
- patch artifact storage
- before/after test summary
- failure classification
- patch risk score
- evidence bundle export

### Phase 4 — Secure execution hardening

- pinned sandbox images
- package-cache strategy
- seccomp/AppArmor profiles
- stronger isolation using gVisor or Firecracker
- resource accounting and artifact quotas

### Phase 5 — GitHub workflow

- branch creation
- PR-ready patch generation
- optional human approval checkpoint
- PR description generation
- no automatic merge by default

### Phase 6 — Research evaluation

- curated bug benchmark
- hidden regression tests
- pass@1 / pass@k
- resolved rate
- regression rate
- iteration/runtime/token metrics
- trajectory quality scoring
- model and policy comparison

## Engineering principles

1. **Verification over generation:** a patch is not successful merely because code was produced.
2. **Least privilege:** read-only is the default; mutations are explicitly authorized.
3. **Untrusted repository:** repository code and tool output are treated as data, not trusted instructions.
4. **Bounded autonomy:** every loop has explicit step and round limits.
5. **Reproducibility:** benchmarks must be deterministic where possible and retain raw results.
6. **Honest measurement:** no model-quality or SWE-bench numbers are claimed without an actual benchmark run.
7. **Human review:** automatic merge/deploy is outside the MVP safety boundary.
