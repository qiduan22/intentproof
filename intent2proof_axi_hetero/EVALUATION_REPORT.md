# Intent2Proof — heterogeneous AXI-Lite interconnect experiment

**Execution classification:** architecture-level checks COMPLETED; new upstream RTL SymbiYosys tasks PREPARED, NOT EXECUTED in this environment.

## Why this experiment

The preceding executed study used three copies of a single ZipCPU FIFO. The new case combines different hardware roles: **two masters, a shared AXI-Lite interconnect, two independently stalling read slaves, and a shutdown controller**. The target is actual open-source [Alex Forencich `verilog-axi` AXI-Lite interconnect](https://github.com/alexforencich/verilog-axi/blob/master/rtl/axil_interconnect.v), including its `arbiter.v` and `priority_encoder.v` dependencies. These upstream files are fetched and their commit SHA and hashes recorded **by the GitHub Actions benchmark**. The repository is publicly archived/deprecated in favor of TAXI; this benchmark uses it as a stable open-source reference design.

The upstream RTL and the newly authored interconnect integration have **not** been elaborated or formally proved locally, as this execution environment has no Yosys/SymbiYosys and cannot access git remotes. This report never promotes architecture-level results to upstream RTL proof.

## Verified requirements and counterexamples

The top-level intent is: after a shutdown request, the FPGA must not start reconfiguration while any read transaction is outstanding or an accepted-to-be-presented read address remains pending. The independent monitor counts upstream AXI-Lite AR handshakes (`ARVALID && ARREADY`) and upstream R handshakes (`RVALID && RREADY`), without relying on the module's own `busy` bits. For read-data ownership, a response must be delivered to the master whose request established its destination; the test slave provides a destination ID tag.

Two injected mutations:
1. `ignore_master1`: the shutdown guard omits the busy/pending state of master 1.
2. `wrong_owner`: a read response is delivered to the other master.

### Actually executed: finite architectural model

The local `architectural_model.py` explores every modeled input choice for a two-master/two-slave serialized architecture with optional bounded downstream delay, response backpressure, round-robin selection, new request admission, and shutdown. It is a **purpose-built protocol model, not a translation of the upstream Verilog**. It includes an independently updated transaction-credit monitor and separate DUT busy indicators. The slave-delay bound is a model parameter; it is **not** a timing guarantee about the physical AXI-Lite components.

| Maximum abstract slave waiting cycles | Reachable states, correct model | Correct safety status | Faulty shutdown witness depth | Wrong-owner witness depth |
|---:|---:|---|---:|---:|
| 1 | 90 | Exhaustively safe in this model | 2 | 3 |
| 2 | 114 | Exhaustively safe in this model | 2 | 3 |
| 3 | 138 | Exhaustively safe in this model | 2 | 3 |
| 4 | 162 | Exhaustively safe in this model | 2 | 3 |

All four correct-model configurations reach meaningful cover conditions, including competing requests, responses from both slaves, backpressure, shutdown while outstanding, and eventual safe reconfiguration. All eight mutant configurations have model-level counterexamples.

### Actually executed: native Z3 contract consistency

Five one-step SMT-LIB obligations were checked against `libz3`:

| Obligation | Result | Interpretation |
|---|---|---|
| Local busy vs. independent credit update inductiveness | UNSAT | No one-step mismatch under the stated common handshake events and invariant |
| No orphan response under credit-contract assumptions | UNSAT | The assumptions prohibit a completion without prior accepted address |
| Correct shutdown condition with outstanding credit | UNSAT | With both master-busy indicators empty and correct mappings, outstanding credit cannot remain |
| Shutdown guard ignoring master 1 | SAT | There is a state with master 1 outstanding and faulty guard permitting shutdown |
| Deliberate response-owner corruption state | SAT | Corrupted delivery can violate the intended response-owner contract |

These establish consistency of **assumed contract equations**; they are not proofs that the imported AXI-Lite interconnect satisfies them. The `*.smt2` inputs, solver results and witness states are included.

## Prepared full upstream RTL experiment (not executed)

`rtl/axi_hetero_top.v` instantiates the real `axil_interconnect` (2 input masters, 2 output slaves) and an authored two-slave AXI read environment. The [file provenance](https://github.com/alexforencich/verilog-axi) is captured at the resolved checkout commit. The generated formal harness tests two address-mapping policies (`separate` and `contended`) and six tasks each:

| Task | Intended result | What it measures |
|---|---|---|
| `full` | PASS | Safety and response-tag checks with real RTL; payload debug port exposed |
| `coi` | PASS | Same properties with no payload debug port (standard synthesis/COI baseline) |
| `contract_candidate` | PASS | A smaller locally authored read-only interconnect summary |
| `mutant_shutdown` | FAIL + VCD | Guard ignores master-1 outstanding request |
| `mutant_route` | FAIL + VCD | Response-valid/ready mapping swapped between masters |
| `cover` | PASS + reachability | Safe shutdown reached after actual responses and outstanding transaction |

**Critical soundness qualification:** a PASS of `contract_candidate` is NOT proof that the abstraction overapproximates the upstream interconnect. Only limited interface observations are checked. A separate verified abstraction/refinement or interface-contract discharge is required before the contract candidate may be used to approve the real RTL. The gate therefore reports `READY_FOR_REVIEW`, not `APPROVED`, even if all 12 tasks have the expected result. The backend compares actual AIG latch/AND-gate counts and measured runtimes; `full` vs `coi` may be identical after ordinary synthesis.

No results are claimed for these 12 upstream RTL tasks yet. The source checkout default `master` is resolved and recorded as a full commit SHA; after the first run, supply that SHA as `upstream_ref` for a fully pinned rerun.

## Why it matters for Intent2Proof

A per-IP FIFO occupancy property cannot detect a response delivered to the wrong AXI master or shutdown of an interconnect with a pending read. These are **cross-component requirements**. The new benchmark targets them while preserving proper ready/valid events, response backpressure, and transaction accounting. The next decisive evidence is the real GitHub Actions SBY artifact, including the source SHA, proof statuses, counterexample waveforms and actual AIG/runtime numbers.

## Reproduce locally (architectural results)

```bash
cd intent2proof_axi_hetero
python3 scripts/architectural_model.py
python3 scripts/contract_smt.py
python3 scripts/plot_arch_results.py
python3 -m unittest discover -s tests -v
```

For GitHub, upload the project folder `intent2proof_axi_hetero` at the repository root and place its workflow file in **repository-root** `.github/workflows/intent2proof-axi-hetero.yml`. Run **Intent2Proof heterogeneous AXI benchmark** in Actions and download `intent2proof-heterogeneous-axi-results` for actual proof audit. Avoid rerunning a stale commit after updating the scripts.
