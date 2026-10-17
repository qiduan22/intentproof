# Intent2Proof AXI Read-Control Contract v2 — Formal Refinement Experiment

**Purpose:** Repair the proven post-reset address-acceptance mismatch in the original candidate contract and attempt a stronger *clock-by-clock* observational miter against pinned upstream AXI-Lite RTL. Check arbitration, registered read responses, backpressure, mapped/unmapped addresses, and reset transitions.

This package is a stand-alone successor to `Intent2Proof_AXI_Refinement_Experiment.zip`. It contains source snapshots, formal harnesses, an SBY generator/runner, regression tests, and local source-grounded Z3 snapshots. **No full RTL proof has been executed in the local environment**; the GitHub runner is required. Read `docs/ASSUMPTIONS_AND_PROOF_SCOPE.md` before interpreting proof status.

## Project layout

```text
Intent2Proof_AXI_Qualified_Contract/
  rtl/                  read-only contract v2, 2 negative controls, miter, formal harness
  third_party/verilog-axi/   unmodified pinned sources and license
  scripts/              run_sby_v2.py, check_local_snapshots.py
  tests/                test_axi_v2.py
  results/local/        executed one-step Z3 snapshots (NOT full RTL proof)
  results/prepared_sby/  generated configurations (NOT executed)
  docs/                 precise contract scope and limitations
```

## Reproduce locally (environment with Yosys, SBY, ABC, Z3)

From repository root:

```bash
python3 -m unittest discover -s Intent2Proof_AXI_Qualified_Contract/tests -v
python3 Intent2Proof_AXI_Qualified_Contract/scripts/check_local_snapshots.py
python3 Intent2Proof_AXI_Qualified_Contract/scripts/run_sby_v2.py \
  --timeout 300 --depth 80 \
  --work Intent2Proof_AXI_Qualified_Contract/results/github_sby
```

To generate without executing, use `--generate-only`. If Yosys/SBY are absent, the runner exits with code 3 and records an explicit blocked status.

## GitHub Actions

Put the directory `Intent2Proof_AXI_Qualified_Contract/` at the **repository root**. Separately create/copy:

```text
.github/workflows/intent2proof-axi-contract-v2.yml
```

The `.github` directory must be at the repository root. If it is hidden by your file-upload tool, create the YAML file directly in GitHub with **Add file → Create new file** and paste the workflow content. Then **Actions → Intent2Proof AXI contract v2 refinement → Run workflow** on the updated branch. Do not rerun a historical commit.

Download the workflow artifact `intent2proof-axi-control-v2-evidence` and upload it into the conversation for independent proof and witness audit. A green workflow run indicates only the benchmark completed with its expected verdicts; always inspect `RUN_STATUS.json` and SBY logs.

## Expected formal tasks (12 total)

- 7 unbounded miter assertions (`abc pdr`): variable requests, master0/slave0, shared-destination contention, distinct destinations, unmapped address, response backpressure, and reset re-entry.
- 3 witness covers (`smtbmc z3`): shared-destination transactions completed by both masters, held response across backpressure, and unmapped-address DECERR.
- 2 deliberately defective control contracts (`abc pdr`): early ARREADY and lost stalled response. A genuine witness is required when these fail.

**No unrestricted general-purpose contract refinement, payload-data preservation, automatic LLM translation, or proof speedup is asserted.**
