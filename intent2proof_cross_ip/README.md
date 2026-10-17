# Intent2Proof — cross-IP composition experiment

This package continues the successful pinned ZipCPU single-FIFO RTL benchmark with a three-FIFO interconnected design. **Offline control-model/SMT results were executed; multi-module Yosys/SymbiYosys RTL tests were prepared but not executed in this environment.**

Read `EXPERIMENT_REPORT.md` for numerical results, methodology, trust boundaries and limitations.

## GitHub Actions

Upload the `intent2proof_cross_ip/` directory into the repository root, then separately create the root workflow:

`.github/workflows/intent2proof-cross-ip.yml`

using the file found at `intent2proof_cross_ip/.github/workflows/intent2proof-cross-ip.yml`. On GitHub, go Actions → **Intent2Proof cross-IP contract benchmark** → Run workflow. Upload the resulting `intent2proof-cross-ip-contract-sby` ZIP back for review.

The source is SHA-pinned and bundled; there is no repository clone or network fetch inside the formal benchmark.

## Locally executed check commands

```
python3 -m unittest discover -s intent2proof_cross_ip/tests -v
python3 intent2proof_cross_ip/scripts/eval_control_model.py
python3 intent2proof_cross_ip/scripts/compose_induction.py
python3 intent2proof_cross_ip/scripts/eval_z3_bmc.py
python3 intent2proof_cross_ip/scripts/plot_results.py
```

## Full RTL verification on a machine with OSS CAD Suite

```
python3 intent2proof_cross_ip/scripts/run_cross_ip.py --work intent2proof_cross_ip/results/sby --timeout 180 --depth 40
python3 intent2proof_cross_ip/scripts/gate_cross_ip.py --work intent2proof_cross_ip/results/sby
python3 intent2proof_cross_ip/scripts/plot_results.py --work intent2proof_cross_ip/results/sby
```

Any missing/unknown SBY result blocks automatic approval.
