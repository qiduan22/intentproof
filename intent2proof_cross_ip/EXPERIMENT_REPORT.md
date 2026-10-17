# Intent2Proof: cross-IP contract abstraction pilot

**Status: actual source-derived model and composition checks completed; new multi-IP SBY RTL checks generated and offline-tested but NOT executed here.**

## Question

Does a property-specific, contract-based control summary allow safe verification of a system-level shutdown condition in an FPGA comprising multiple IP instances, and can it offer a benefit beyond standard cone-of-influence reduction?

## Design provenance and assembly

- Pinned open-source RTL: ZipCPU `wb2axip/rtl/sfifo.v`, commit `2e8d3bc2d26ddc33d1881022a2a2b9d3f0c16b9b`, SHA-256 `76a653781f1ecca1c1da92c4e5105ecd5d0f832b13cbfd31300ec88d9947e0c1`; copied verbatim from the previously successful upstream SBY execution artifact. The source retains its public-domain header.
- New authored integration logic: **two ingress FIFOs + round-robin interconnect + one sink FIFO + shutdown latch**. All three FIFOs instantiate the actual pinned upstream module in the concrete RTL variant; they are repeated instances of one upstream IP, not three independently sourced IPs. Same synchronous clock, arbitrary ingress/egress backpressure.
- Approved safety property: reconfiguration must not start while any accepted data remains buffered. An independent monitor increments on accepted ingress transfers and decrements on accepted sink outputs. The accepted/delivered event definitions reflect actual ready/full/empty interface handshakes; no use of a DUT internal "global pending" status flag.
- Deliberate negative control: omit sink-FIFO emptiness from the reconfiguration guard. The bad implementation can start reconfiguration with data still buffered at the sink.
- Parameter variations: LGFLEN=2,3,4 (capacity 4,8,16); BW=8 in this integration study, `OPT_ASYNC_READ=1`, `OPT_WRITE_ON_FULL=0`, `OPT_READ_ON_EMPTY=0`.

## Results genuinely executed in this local environment

### Exhaustive source-derived control model (not full RTL)

| Capacity per FIFO | Reachable correct-model states | Correct safety/conservation | Mutant | Shortest witness |
|---:|---:|---|---|---:|
| 4 | 354 | Exhaustively safe | Violation | 2 transitions |
| 8 | 2,290 | Exhaustively safe | Violation | 2 transitions |
| 16 | 17,106 | Exhaustively safe | Violation | 2 transitions |

Each correct model covered simultaneous ingress acceptance, nonempty source FIFOs, occupied sink FIFO, shutdown with outstanding data, and a reachable safe `reconfig_start`. The transition-system enumeration permits all 16 valuations of `wr_a`, `wr_b`, `rd_sink`, and `shutdown_request` per step. Source FIFO control equations are transcribed from pinned RTL, not automatically elaborated.

**Concrete mutant witness** (capacity 4):
1. Ingress B accepts one item, pending = 1, source B occupancy = 1.
2. Shutdown is requested; the item transfers from ingress B to sink FIFO. Source FIFOs become empty while the sink remains occupied, pending = 1.
3. The faulty guard (`latched && empty_A && empty_B`) asserts reconfiguration; the correct guard additionally checks `empty_sink`, so it does not.

### Inductive contract-composition obligations (native Z3 SMT)

Across each capacity, the following quantifier-free checks completed:

- Counterexample to one-step conservation induction under the interface contracts: **UNSAT**.
- Counterexample to legal capacity preservation under handshake rules: **UNSAT**.
- Counterexample to `reconfig_start -> pending = 0` under the *correct* shutdown contract: **UNSAT**.
- Counterexample to that same property under the deliberately faulty shutdown condition: **SAT**.

**12 of 12** contract-level SMT obligations returned the expected satisfiability result. These mathematical checks justify the composition of the modeled control contracts, but are **not** a verified RTL binding of the authored interconnect.

### Bounded model checking with three encodings (native Z3)

- At bound 6: 9/9 correct-encoding checks returned UNSAT for a violation, and 9/9 faulty variants returned SAT.
- At bound 10 (capacity 4 only): all 3 correct encodings returned **UNKNOWN** under a 4-second solver limit; all 3 faulty encodings returned SAT. This is not an error in the design and does not constitute a proof.
- Median six-step wall times across three capacities: augmented-source-control 0.218s, standard control COI 0.204s, contract count summary 0.234s. **No runtime speedup over standard COI was demonstrated.** These are tiny model checks and are not Yosys/ABC runtimes.
- Median six-step SMT size: augmented 29,270 bytes, COI 21,845 bytes, contract summary 15,152 bytes. Contract summary is about **30.6% smaller** than standard COI for this encoding, but the empirical solver times do not improve.

### Theoretical state budgets (not Yosys/ABC measurements)

The three `sfifo` instances together contain payload storage as well as read/write pointers, occupancy, and empty flags. For this control-only requirement, ordinary dependency slicing already removes most payload and pointer state. Our count contract replaces each registered empty flag with `occupancy==0` after the unit-level property is discharged.

| FIFO depth | Declared-state budget incl. data | Standard COI control bits | Count-contract control bits |
|---:|---:|---:|---:|
| 4 | 133 | 19 | 16 |
| 8 | 239 | 23 | 20 |
| 16 | 441 | 27 | 24 |

The numbers are computed from selected RTL register declarations and independent monitor/control registers; they are **not** extracted synthesis statistics. The incremental count-contract saving over COI is only three bits, so substantial proof speedups should not be inferred.

## New real-RTL SBY benchmark (generated, not executed)

The `scripts/run_cross_ip.py` runner generates **18 formal tasks** across 3 capacities:

1. `full`: original pinned RTL with payload outputs exposed (structural baseline).
2. `coi`: the same original RTL with a control-only verification interface (standard structural COI baseline).
3. `contract`: a count-only FIFO contract model under the same global requirements.
4. `unit_contract`: independently prove `o_full`, `o_empty`, and `o_fill` match between pinned upstream RTL and its contract for the exact parameter setting.
5. `mutant`: concrete original FIFOs plus deliberately wrong system-level shutdown logic, expected `FAIL` with VCD counterexample.
6. `cover`: non-vacuity objectives on the concrete RTL, expected `PASS`/covered.

The acceptance gate requires all original and contract tasks to pass, all mutants to fail **with recorded witnesses**, every cover task to pass, and every unit contract to be discharged. Missing results, inconclusive tasks, or absent witnesses fail closed. Logs, AIG model digests, latches/gates and wall times are retained for direct comparison; it remains possible that ABC reduces `full` and `coi` to the same AIG.

### Why the SBY run is still necessary

This environment has no `yosys`, `sby`, `z3` executable, or network access to execute the new multi-module RTL benchmark. Earlier upstream SBY results for the single `sfifo` IP provide helpful evidence for its control invariants, but do not prove the newly authored merge/shutdown RTL. The complete cross-IP claim requires the new pinned-source benchmark.

## Reproduce local checks

```bash
cd intent2proof_cross_ip
python3 -m unittest discover -s tests -v
python3 scripts/eval_control_model.py
python3 scripts/compose_induction.py
python3 scripts/eval_z3_bmc.py
python3 scripts/plot_results.py
python3 scripts/run_cross_ip.py --generate-only
```

The composition/BMC scripts use the native system `libz3` accessed through Python `ctypes`; no Python `z3` package is required. The local program deliberately records UNSAT, SAT and UNKNOWN separately. `matplotlib` is required for plots.

## Reproduce true full-RTL verification via GitHub Actions

Put the package's `intent2proof_cross_ip/` directory in your repo root. Put its supplied workflow YAML **at the repository root** `.github/workflows/intent2proof-cross-ip.yml` (not nested inside `intent2proof_cross_ip/`). Commit both. In GitHub Actions, choose **Intent2Proof cross-IP contract benchmark** → **Run workflow**, then download the `intent2proof-cross-ip-contract-sby` artifact. Upload it for analysis and inclusion of verified RTL figures into the proposal.

## Interpretation

The experiment demonstrates feasibility of describing global safety using small contract-level obligations and finds a cross-IP shutdown error that a local FIFO correctness proof alone cannot detect. It **does not** yet establish unique algorithmic novelty or a proof-runtime improvement over established COI. The decisive remaining evidence is the upstream RTL contract-discharge and comparative AIG/proof measurements for the interconnected system.
