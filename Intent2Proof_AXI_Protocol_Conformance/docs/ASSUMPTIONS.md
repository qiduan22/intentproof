# Scope, protocol assumptions, and claims for AXI legal-slave v3

## Prior issue addressed

The v2 covers generated `m_rvalid` responses without any downstream
`m_arvalid && m_arready` handshake. The v3 response environment is a real
Verilog module with registered state. Each of two destination slaves:

- has a capacity of one outstanding read;
- advertises `m_arready` only when idle and `allow_accept` is asserted;
- captures a downstream read-address handshake;
- may delay `m_rvalid` arbitrarily but only AFTER it has captured the address;
- maintains `m_rvalid`, `m_rdata`, and `m_rresp` while waiting for `m_rready`;
- returns to idle when the response handshake is completed;
- discards the pending transaction on synchronous reset.

This is AXI-Lite read-side protocol-conforming *within this explicit supported
subclass*, not a universal AXI4/AXI-Lite verification model. No fairness or
response deadline is imposed. The formal checker may choose ready/response
enables nondeterministically, including infinite waits.

## Independent monitor

`monitor_pending[j]` is updated ONLY from `real_m_arvalid[j] && m_arready[j]`
and `m_rvalid[j] && real_m_rready[j]` handshakes. It is NOT copied from the
slave's internal `pending` state. Each response-valid signal must have a
previously observed accepted read; requests may not be accepted twice on an
occupied slave; responses must hold under backpressure. The upstream miter
still compares both RTL implementations against the SAME slave inputs.

For a *negative control* only, `INJECT_UNSOLICITED_RESPONSE=1` generates a
response before any address acceptance, which the monitor must reject.

## What a future PASS establishes

Unbounded ABC PDR safety checks would establish cycle-accurate equality for
the read-control observations selected in `axi_read_control_miter_v2.v`,
including ARREADY, RVALID, downstream ARVALID and RREADY, response status when
valid, and downstream addresses when valid, under this legal-slave environment
and the approved reset and master-stability assumptions. Cover witnesses would
also show actual downstream AR acceptance, actual downstream response
completion, and matching upstream response completion (at least two for
master0/master1 contention). Mutant failures validate test sensitivity.

The slave model is driven by the **original RTL's downstream outputs** and
the abstract contract receives the same response inputs. This is a
reference-driven, matched-environment equivalence test. It is NOT a complete
compositional refinement proof for independently connected real and abstract
circuits under all physically possible environments.

## What is NOT established

- AXI write-address/data/response handling, or read-data payload integrity.
- More than one outstanding transaction per downstream slave.
- Full AXI-Lite protocol conformance across all independent peers.
- Liveness or bounded response times without fairness assumptions.
- All reset sequences: the benchmark constrains an initial reset and then
  deasserted reset. No mid-transaction reset is exercised by these tasks.
- Timing, CDC, physical implementation, synthesis PPA, or hardware safety.
- Automated LLM intent-to-assertion translation or automated abstraction.
- A sound *general* trace-inclusion relation for arbitrary use of the contract.
- Any runtime improvement over standard cone-of-influence elimination.

## Proof-quality rules

- A cover is not a universal proof, and existence of one valid trace does not
  show every possible transaction completes.
- `UNKNOWN`, `TIMEOUT`, missing logs, or unmatched test status blocks
  promotion to even this restricted qualification.
- An expected mutant `FAIL` requires a real witness VCD.
- The CI exit code is not a substitute for inspecting every SBY log and VCD.
- The benchmark remains `REVIEW_REQUIRED` as a product change-gate decision.
