# Scope, assumptions, and proof obligations

## Origin and trusted boundaries
- Real RTL is `axil_interconnect.v` from `alexforencich/verilog-axi`, pinned by a commit SHA and SHA-256 hashes. Dependencies `arbiter.v` and `priority_encoder.v` are similarly pinned. Source files are copied unmodified, under their upstream copyright/license.
- Candidate `axi_read_control_contract_v2.v` is manually authored and is **not a discovered/automatically extracted contract**. Its arbiter instance is the same upstream arbiter as in the DUT, so this experiment does **not** independently qualify a changed arbitration algorithm.
- The miter provides **paired-input observational equality** under assumptions. This is not a general proof of trace inclusion with different external scheduling or arbitrary unmatched abstract environments.

## Hard scope restrictions
1. Two AXI-Lite source/read masters, two destination/read slave ports, 16-bit address, 32-bit data, fixed 256-byte regions starting at addresses `0x0000` and `0x0100` (each uses 8 variable low address bits). Destination/response signal names use AXI's master/slave port naming; data flows from masters through the interconnect to slaves.
2. `AWVALID` and `WVALID` are tied low; **write behavior is not compared**.
3. `ARPROT` is tied to zero; protection/security-address features are not modeled here.
4. Matched exogenous inputs are given to both concrete and candidate instances at the same sampling edge: `S_ARVALID`, `S_ARADDR`, `S_RREADY`, `M_ARREADY`, `M_RVALID`, `M_RRESP`, `M_RDATA`, `rst`.
5. Observables checked for cycle-accurate equality: `S_ARREADY`, `S_RVALID`, `M_ARVALID`, `M_RREADY`, plus `M_ARADDR` when either M_ARVALID is asserted and `S_RRESP` when either S_RVALID is asserted. `S_ARVALID & S_ARREADY` and `S_RVALID & S_RREADY` are derived acceptance/completion events and are also exposed in traces.
6. `S_RDATA` is **not modeled in the contract**. Safety properties depending on read payload values, data ordering, or error-data behavior are outside this experiment.
7. Source masters keep `ARVALID` and `ARADDR` stable while not yet accepted, except on reset. Slave `RVALID`, `RRESP`, `RDATA` remain stable until a read-response handshake, except on reset. These are standard protocol-style assumptions imposed by the formal harness, not properties proved about external software/devices.
8. Reset is asserted on the first sampled edge, then normally released; a separate proof mode permits reset re-entry. Signals are compared only outside reset. This does not prove asynchronous reset behavior or multi-clock CDC correctness.
9. Downstream slave responses are not fully tied to accepted AR transactions in the miter harness. The comparison may therefore include externally invalid responses; this is conservative for paired-interface equality but does not substitute for a complete formal AXI protocol environment.

## Meaning of a passing proof
If **all required unbounded miter safety properties** are proved using ABC PDR and the supporting covers and negative controls complete, the benchmark can support cycle-accurate equivalence of the specified **read-control observations only** under the declared configuration/assumptions. That is a property of a manually authored candidate; it does not justify the general `Intent2Proof` abstraction algorithm.

A PASS on one mode, a bounded UNSAT result, or a proof on the reduced contract alone is not qualification. A FAIL from a corrected-candidate miter requires a concrete witness audit and correction or a more explicit justified restriction. The script never approves a design for production use.

## Follow-up tests beyond this candidate
- Check a contract for response payload and ordering (RDATA/RRESP under transaction-ID assumptions), including read errors and unmapped accesses.
- Remove reliance on the identical upstream arbiter by proving an independent abstract scheduler's fairness/grant relation.
- Prove a simulation or trace-refinement relation for nondeterministic and potentially stuttering abstraction; matched-input miter equality is only one useful special case.
- Expand to read/write AXI-Lite, full AXI bursts, multi-clock/CDC cases, address configuration variants, and genuine high-load contention.
- Compare actual solver cost with full RTL and vendor COI across repeats and pinned configurations; no runtime speedup is claimed here.
