# Intent2Proof: AXI contract refinement and genuine contention benchmark

This experiment follows the successful heterogeneous AXI-Lite benchmark. It tests whether the smaller bridge actually preserves read-handshake behavior of the pinned upstream `axil_interconnect` and independently checks that **two** read masters contend for the **same** slave.

## What has actually run

- Source-anchored post-reset ready/acceptance SMT checks: 3/3 expected SAT/UNSAT outcomes using native libz3.
- Source/runner/offline unit tests: 10/10 passed.
- Full RTL SymbiYosys tasks: generated; **NOT run locally** because OSS CAD Suite is unavailable in this container.

Details: `EXPERIMENT_REPORT.md`.

## GitHub upload structure

Put these at the **repository root** (not under an extra wrapper directory):

```
.github/workflows/intent2proof-axi-refinement.yml
Intent2Proof_AXI_Refinement/README.md
Intent2Proof_AXI_Refinement/scripts/run_refinement.py
Intent2Proof_AXI_Refinement/rtl/...
Intent2Proof_AXI_Refinement/third_party/verilog-axi/rtl/...
```

Go to GitHub **Actions**, choose **Intent2Proof AXI refinement and true contention**, then **Run workflow** on the branch containing these files. Download artifact `intent2proof-axi-refinement-evidence` and upload it to ChatGPT.

## Local commands (optional)

```
python3 -m unittest discover -s Intent2Proof_AXI_Refinement/tests -v
python3 Intent2Proof_AXI_Refinement/scripts/run_refinement.py --generate-only
python3 Intent2Proof_AXI_Refinement/scripts/run_refinement.py --timeout 180 --depth 80
python3 Intent2Proof_AXI_Refinement/scripts/local_source_semantics.py
```

`local_source_semantics.py` requires libz3 and is not a substitute for SBY. `run_refinement.py` refuses to claim a formal proof without Yosys/SymbiYosys. Even a success from the prepared workflow **rejects** cycle equivalence when the expected miter counterexample is present; do not confuse a green workflow with a qualified abstraction.

Upstream source: https://github.com/alexforencich/verilog-axi at commit `516bd5dadc3365b7f9e225d2af8fe0b8d804fe53`. The third-party license is bundled as `third_party/verilog-axi/COPYING`.
