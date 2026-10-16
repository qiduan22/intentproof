# Intent2Proof — pinned upstream RTL validation: actual execution status

Date: 2026-10-16 (current session). **Source-level verification: BLOCKED; not run.**

## What was attempted here

- Re-ran the benchmark's full-preflight command. The environment has Git but lacks Yosys, SymbiYosys (`sby`), and a standalone `z3` executable; therefore the runner exited with code 2 **before reading upstream RTL or running any SBY tasks**.
- Verified that container DNS cannot resolve github.com/raw.githubusercontent.com; neither an immutable Git checkout nor an upstream source checksum could be established locally.
- Ran the repaired generator's seven offline regression tests successfully. These use an explicitly invented fixture, **not actual upstream source**.
- Tested the strict acceptance gate on missing/unknown results. It exited nonzero and emitted `accepted: false`, correctly refusing to treat unrun checks as proofs.
- Added a GitHub Actions workflow that installs OSS CAD Suite, resolves an exact upstream commit SHA at job start (or takes one supplied by the operator), executes the RTL proofs, requires concrete mutant witnesses, and uploads the raw outputs even if a step fails.

## Discovered and corrected benchmark-harness defects

1. **Incorrect SBY input filenames:** the previous `[script]` referenced `sfifo.v bench.v` but its `[files]` supplied `source_synthesis_view.v` and case-specific names. The corrected SBY configurations use explicit aliases (`sfifo.v <source>`, `bench.v <wrapper>`, and `ref.v <reference>`) as supported by SBY. Offline tests assert that aliases and script references match.
2. **Incorrect expected-mutant handling:** SBY typically returns a nonzero exit when a property fails. The old status interpreter dismissed all nonzero exits before inspecting the `status` file, so an expected injected mutation could never be reported as `PROPERTY_FAILED`. The corrected interpreter accepts `FAIL` from a completed SBY attempt with nonzero exit, while `TIMEOUT`, tool errors, and missing status remain unresolved.
3. **Fail-closed reporting:** added source SHA/manifest verification, mandatory passing equivalence proof for the control reference, actual counterexample witness requirement for injected mutant, required cover and structural measurements, and a strict verdict required before benchmark plots are emitted.

## Evidence/status summary

| Item | Status |
|---|---|
| Pinned upstream source fetched in this environment | NO |
| Yosys elaboration of upstream `sfifo.v` | NOT RUN |
| SBY full/COI/contract equivalence proofs | NOT RUN |
| SBY mutant counterexample/cover | NOT RUN |
| SBY runtime or verified state-bit reduction measurements | NOT AVAILABLE |
| Offline wrapper/preprocessor/status/gate tests | **7/7 PASS** |
| Full benchmark preflight | BLOCKED: missing required executables |
| Automatic acceptance decision | **REJECTED**: no executed result files |
| Remote CI workflow | PREPARED, **not executed** |

**Do not publish any new full-upstream RTL proof, performance, soundness, or speedup claim based on this delivery.** The previous manually source-derived Z3 plots remain historical model-level evidence only.

## How to complete the blocked upstream experiment

1. Place this package in a GitHub repository, preserving `.github/workflows/intent2proof-upstream.yml`. Open **Actions → Intent2Proof pinned RTL verification → Run workflow**. Optionally supply a 40-digit pinned `wb2axip` commit SHA. Otherwise the workflow resolves the current upstream master commit SHA **once** and records it before executing any task.
2. The official `YosysHQ/setup-oss-cad-suite@v4` action provisions Yosys/SBY/Z3. See https://github.com/YosysHQ/setup-oss-cad-suite.
3. Download the workflow artifact `intent2proof-pinned-upstream-sby`, which contains immutable source metadata, per-task statuses, logs, counterexample traces, measured synthesis model statistics, and figures **only if strict verification passed**.
4. If the artifact contains `ci_verdict.json` with `accepted: true`, its verified figures can be referenced in a new revision of the proposal with exact commit, assumptions, tool versions, timing, and limits. If not, investigate per-task logs and report UNKNOWN/FAIL rather than upgrading the claims.

**Local Linux/WSL command** (with OSS CAD Suite installed and an actual internet connection):

```bash
cd intent2proof_upstream_validation
python3 -m unittest discover -s tests -v
python3 upstream_benchmark.py --commit <40-character-SHA> --work results/upstream_sby --timeout 180
python3 gate_upstream_results.py --work results/upstream_sby
python3 plot_upstream_results.py --work results/upstream_sby
```

All tasks use the same source revision and explicit parameter choices, and the `contract` test proves sampled control-output equivalence rather than presupposing it. This does not establish general-purpose automated abstraction synthesis or physical timing closure.
