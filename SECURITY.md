# Security

## Threat model

Forge executes software-development actions in a user-selected workspace. Treat repository files, issue text, model output, and command output as untrusted input.

## Current controls

- Workspace path canonicalization prevents `../` escape.
- Commands run without a shell.
- Child processes do not receive `OPENAI_API_KEY` or `GITHUB_TOKEN`.
- Writes are disabled unless explicitly approved.
- File reads have a size limit.
- Tool names are allow-listed by the registry.
- Model output is parsed as structured JSON before tool execution.

## Deployment guidance

Run Forge inside a dedicated non-privileged container for untrusted repositories. Do not mount host credentials, Docker sockets, SSH keys, cloud credential directories, or broad home-directory paths into the agent environment. Add network egress controls before enabling unattended execution.

## Known limitations

The current repository implementation is a secure core, not yet a complete hostile-code sandbox. Arbitrary test suites can still consume CPU/memory or attempt network access when run on the host. The production milestone will add resource quotas, isolation, network policy, approval gates, and resumable execution state.
