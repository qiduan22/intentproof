# Run genuine upstream RTL validation

This package fixes the previously prepared benchmark and supplies an automated cloud-run option.

## Method A: GitHub Actions (recommended if Yosys is not installed)

Copy **all** package contents (including `.github/workflows/intent2proof-upstream.yml`) into a GitHub repository. Commit/push the files and select **Actions → Intent2Proof pinned RTL verification → Run workflow**. The workflow downloads OSS CAD Suite and checks out a frozen Git commit of ZipCPU `wb2axip`. It runs fifteen tasks (3 FIFO configurations x full/coi/contract/mutant/cover), uploads logs and traces even if a task fails, and renders figures only when the strict gate passes. The workflow itself has not been run in the present environment.

A GitHub Actions run needs internet and a repository whose workflow is authorized to run. Nothing is pushed automatically by this package.

## Method B: Linux/WSL with OSS CAD Suite

Install OSS CAD Suite from https://github.com/YosysHQ/oss-cad-suite-build and activate its environment. Then:

```bash
cd intent2proof_upstream_validation
python3 -m unittest discover -s tests -v
python3 upstream_benchmark.py --work results/upstream_sby --timeout 180 --commit <40-hex-sha>
python3 gate_upstream_results.py --work results/upstream_sby
python3 plot_upstream_results.py --work results/upstream_sby
```

Use `python3 upstream_benchmark.py --self-test` for an offline generator check (not formal RTL verification). Before publishing results, verify the exact source fingerprint, approved environment/clock/reset assumptions, actual SBY PASS/FAIL status, and the equivalence proof; consider independent source-to-elaboration comparison for the synthesized source view.

## Executed in this ChatGPT environment

Only seven offline tests passed; the real upstream benchmark preflight and strict gate both stopped with exit status 2. See `intent2proof_upstream_validation/CURRENT_EXECUTION_STATUS.md` and the `attempt_logs` folder for exact output.
