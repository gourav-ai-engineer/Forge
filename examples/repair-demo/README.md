# Forge repair fixture

This deliberately broken calculator gives Forge a deterministic end-to-end exercise. The implementation subtracts instead of adding, so the tests fail before a repair.

From the Forge repository root, build the sandbox image and run:

    docker build -f Dockerfile.sandbox -t forge-sandbox:local .
    python forge_cli.py "Fix calculator.py so the tests pass; make the smallest change and review the diff." --repo examples/repair-demo --allow-writes --sandbox --json

The fixture is intentionally outside the root project's configured testpaths, so it does not make the main repository CI suite fail. The repair command needs an OpenAI API key to use the model planner. Without it, Forge performs only the deterministic inspection baseline.
