# Intent2Proof — Protocol-aware AXI-Lite slave refinement (v3)

## Question addressed

Can the corrected v2 read-control contract remain cycle-equivalent to the pinned
open-source AXI-Lite interconnect **when responses are guaranteed to follow
actual accepted downstream requests**, and can the benchmark demonstrate real
(two-master, one-slave) contention rather than unsolicited responses?

## Prior evidence and motivation

The uploaded v2 evidence (audited previously) contained seven PDR proofs of
read-control cycle equivalence under the then-current environment. However,
the “true contention” cover showed upstream completions without *any*
`m_arvalid && m_arready` downstream handshake. Consequently, that witness
could not support a legal AXI-Lite transaction-completion claim. The new v3
benchmark repairs the **verification environment**; the pinned upstream RTL,
read-control contract, and miter are retained unchanged.

## Protocol-conforming slave model

`rtl/axi_legal_read_slave_pair.v` provides two read-only AXI-Lite destinations.
For each slave, the model accepts at most one outstanding read, registers the
accepted address, and generates its response only in a later clock step. It
holds `RVALID`, `RRESP`, and `RDATA` stable until `RREADY` completes the
response. Readiness and response generation may be arbitrarily delayed; no
liveness/fairness assumption has been introduced. The model supports a
separate deliberately illegal `RVALID` mutation.

The benchmark independently maintains `monitor_pending` using **downstream
handshake events**, not the slave's own busy flag. It asserts that every
RVALID follows an accepted AR, every downstream completion has an outstanding
request, no request is accepted while occupied, and stalled responses remain
stable. The miter additionally checks the same cycle-by-cycle read-control
observations as in v2.

## Executed local results (17 October 2026)

The container lacks Yosys, SBY, and executable Z3, so the **new full-RTL
experiment has not been executed**. The following results are from an
independent Python *reference-state model*, not Verilog elaboration:

| Check | Executed outcome |
|---|---:|
| One slave — reachable protocol-control states | 3 |
| Two independent slaves — reachable protocol-control states | 9 |
| One slave — state/input transitions exhaustively examined | 48 |
| Two slaves — state/input transitions exhaustively examined | 2,304 |
| Illegal unsolicited-RVALID mutation | Detected |
| Two accepted read requests and two matched completions | Witness in 6 abstract steps |
| Python harness/offline regression tests | 18 passed |

The Python state model excludes source arbitration and the original AXI-Lite
interconnect. Therefore these results demonstrate only the *internal
coherence* of the intended legal response policy and test harness.

Figure 1 plots the six-step Python reference witness; Figure 2 plots the
three and nine reachable protocol states. Neither figure represents RTL
solver performance or upstream verification results.

## Real RTL test matrix — GENERATED, NOT EXECUTED locally

| Task class | Tasks | What the GitHub SBY run will check |
|---|---:|---|
| PDR safety | 5 | Original interconnect versus v2 contract with legal slave; unrestricted/legal source, shared destination, distinct destinations, unmapped request, response stalls |
| Covers | 4 | True shared contention with **two downstream AR handshakes and two matched R handshakes** plus both upstream completions; two consecutive upstream stall cycles then completion; unmapped DECERR without downstream acceptance; separate destination completions |
| Negative controls | 3 | Early-ready contract, dropped stalled response contract, intentionally unsolicited slave response |
| **Total** | **12** | Fail-closed statuses and witness evidence |

All tasks use pinned upstream `axil_interconnect.v`, `arbiter.v`, and
`priority_encoder.v` at commit
`516bd5dadc3365b7f9e225d2af8fe0b8d804fe53` (SHA-256 checked).
GitHub results must contain SBY PDR proof evidence, bounded cover witness
traces, negative-control counterexamples, and status records for all tasks.

## Soundness and applicability limits

This remains a scope-restricted **read-side control equivalence test**.
The slave is driven by the real interconnect's downstream requests, and both
the real/abstract implementations see the same slave response pins. It is not
an independently composed full-system trace-inclusion proof. The slave supports
one outstanding request per destination. Read payload ordering/integrity,
AXI write operations, data-dependent timing, multi-clock/CDC effects, and
unbounded fairness/liveness are not checked. The initial reset and master
hold-until-accepted rules are built into the benchmark.

This follow-up **does not establish a speedup or reduce AIG state**; the experiment
is intended to close the realistic-transaction evidence gap first. It will be
appropriate to compare solver cost and model size only after the protocol-
qualified run has passed and its counterexamples/covers have been audited.

## What to do next

Commit `Intent2Proof_AXI_Protocol_Conformance/` and the repository-root
workflow `.github/workflows/intent2proof-axi-protocol-v3.yml` to
`qiduan22/intentproof`. In GitHub Actions run **Intent2Proof AXI v3 legal-
transaction refinement** from the updated branch. Download
`intent2proof-axi-v3-legal-transaction-evidence` and upload it here. Even a
green workflow must be inspected at the per-task level; `UNKNOWN`,
missing/unreached covers, or an unexpected mutant outcome blocks qualification.
