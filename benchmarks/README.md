# Forge Benchmark Suite

This benchmark measures **runtime reliability and safety guarantees** of Forge. It deliberately does not invent model-quality numbers. Results are generated locally from the checked-out commit.

## What is measured

| Metric | Meaning |
|---|---|
| Offline success rate | Percentage of deterministic inspection runs that finish successfully |
| Safety gate pass rate | Percentage of write/commit authorization checks that correctly reject unauthorized mutations |
| Path traversal rejection | Whether workspace boundaries reject `../` and absolute-path escapes |
| Credential filtering | Whether sensitive environment variables are removed from child processes |
| Median runtime | Median wall-clock duration of the deterministic benchmark cases |

## Run

```bash
python benchmarks/run_benchmark.py
```

JSON output can be saved for experiment tracking:

```bash
python benchmarks/run_benchmark.py --json > benchmark-result.json
```

The generated result contains the commit SHA when Git metadata is available, so resume claims can be tied to a reproducible repository state.

## Resume policy

Only report numbers that were produced by an actual benchmark run. Do not copy the example values in documentation into a resume. A strong resume bullet should look like:

> Built Forge, a bounded autonomous software-engineering agent with guarded tool execution and recovery loops; achieved **X% deterministic benchmark success** across **N cases** while enforcing workspace and mutation safety gates.

Replace **X** and **N** with measured values from `benchmark-result.json`.
