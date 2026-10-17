# Intent2Proof — heterogeneous AXI benchmark

**Local proof scope**: 4 exhaustively explored architectural configurations, 8 injected mutations, 5 Z3 one-step SMT contract obligations. These are not proofs of upstream Verilog.

**Upstream RTL scope**: 12 real-RTL SymbiYosys tasks prepared, awaiting execution on OSS CAD Suite / GitHub Actions.

* `EVALUATION_REPORT.md`: details and limitations.
* `rtl/`: authored AXI master/stop-controller integration, two read slaves, and an explicitly **unqualified** candidate contract bridge. Upstream `verilog-axi` is fetched by `scripts/run_axi_sby.py` rather than vendored without a pinned SHA.
* `scripts/architectural_model.py`: exhaustive model-level checks and witness traces.
* `scripts/contract_smt.py`: native Z3 SMT-LIB composition checks.
* `scripts/run_axi_sby.py`: source checkout with commit/hash manifest, 12 formal tasks, and real-RTL measurements.
* `scripts/gate_axi.py`: fail-closed results checking; outputs `READY_FOR_REVIEW`, not automatic contract approval.
* `.github/workflows/intent2proof-axi-hetero.yml`: GitHub Actions runner.
* `tests/`: 12 passing offline tests.

**Start GitHub validation:** In your existing `qiduan22/intentproof` repository, add `intent2proof_axi_hetero/` at the root, then copy `.github/workflows/intent2proof-axi-hetero.yml` into the **repository root** `.github/workflows/`. Start a **new** Actions run on the updated commit. Once a run is available, pass its resolved upstream SHA as `upstream_ref` for a pinned rerun.

The comparison to the previous three-FIFO study is intentional: this benchmark adds request/response routing, read backpressure, and an externally sourced shared AXI-Lite interconnect. All statements about speedup/equivalence require the future real-RTL artifact.

### If GitHub hides `.github` during upload

On the repository **Code** page choose **Add file → Create new file** and enter
`.github/workflows/intent2proof-axi-hetero.yml` as the filename; paste the
workflow content from this package. Commit to the default branch. Then launch
**Actions → Intent2Proof heterogeneous AXI benchmark → Run workflow**. Start a
**new run on the updated commit**, not `Re-run jobs` on an older commit.

After the first run, read `results/upstream_sby/manifest.json` in the downloaded
artifact for `resolved_commit`. On the next run set the `upstream_ref` input to
that SHA to reproduce the same upstream RTL revision.
