# Intent2Proof AXI v3 — Protocol-conforming slave and legal contention

This is the next experiment after **AXI control contract v2**. It repairs a
benchmark-environment weakness discovered in the user-supplied v2 artifact:
responses appeared without prior downstream accepted addresses.

The real external RTL is a pinned `alexforencich/verilog-axi` AXI-Lite
interconnect (two masters, two destinations), with the prior hand-coded
registered-read-control contract under comparison. The two response channels
are now driven by a separate, read-only slave model and checked by an
independent scoreboard that observes actual bus handshakes.

## What is new

- `rtl/axi_legal_read_slave_pair.v`: one-outstanding-per-slave, read-only
  responder that cannot generate an unsolicited response and holds responses
  stable under backpressure.
- `rtl/axi_protocol_v3_formal_bench.v`: v2 RTL miter connected to two legal
  slaves, with separate protocol assertions and real downstream handshake
  counters in its cover goals.
- Five formal PDR proof variants, four non-vacuity covers, and three negative
  controls (contract early-ready, contract lost response, and illegal slave).
- Strict fail-closed GitHub test runner and a local Python reference-state
  check. No upstream RTL proof is claimed until GitHub returns the evidence.

## Files

- `third_party/verilog-axi/rtl/`: pinned unmodified upstream sources (MIT).
- `rtl/`: v2 correct/mutated contracts, original miter, legal slave, v3 bench.
- `scripts/run_sby_protocol_v3.py`: generates 12 SBY tasks and runs them.
- `scripts/check_local_protocol.py`: executable *Python reference-model*
  exhaustive check; cannot establish correctness of Verilog.
- `tests/test_protocol_v3.py`: harness regression tests.
- `docs/ASSUMPTIONS.md`: precise boundary of any eventual proof claim.
- `workflow/intent2proof-axi-protocol-v3.yml`: copy to repository-root
  `.github/workflows/intent2proof-axi-protocol-v3.yml`.

## Reproduction

```bash
python3 -m unittest discover -s Intent2Proof_AXI_Protocol_Conformance/tests -v
python3 Intent2Proof_AXI_Protocol_Conformance/scripts/check_local_protocol.py
python3 Intent2Proof_AXI_Protocol_Conformance/scripts/run_sby_protocol_v3.py \
  --timeout 450 --depth 120 \
  --work Intent2Proof_AXI_Protocol_Conformance/results/github_sby
```

This runtime lacks Yosys/SBY; the final command is expected to record
`BLOCKED_MISSING_TOOLS` locally rather than claiming success. Run the GitHub
workflow to generate actual RTL proof evidence. The runner carries the same
upstream source pins and checks SHA-256 before generating formal tasks.

## Qualification policy

Only the scoped cycle-accurate read-control relation under the explicitly
modeled legal-slave environment could be qualified by these tasks. All broader
refinement, timing, write/data, LLM, and commercial speedup claims remain open.
