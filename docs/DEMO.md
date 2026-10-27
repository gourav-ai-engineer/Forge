# Forge — Demo Guide

The public `demo/` page is a deterministic UI simulation for portfolio visitors. It intentionally does not claim to execute arbitrary repository code or expose an API key.

The authoritative Forge runtime is the Python package under `forge/` and the CLI entry point `forge_cli.py`.

## Live-model verification

Use the local runtime with an OpenAI API key and a disposable sample repository. The key stays in the environment and is never written to the workspace.

## Portfolio note

The demo should be described as a product walkthrough, while the repository README and CI establish which behaviors are actually implemented and verified.
