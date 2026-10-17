# Refinement experiment v2 versus previous candidate

- Replaced combinational `S_ARREADY` with a source-matching registered output and `ST_IDLE → ST_DECODE → ST_READ → ST_WAIT` transition structure.
- Uses the **pinned original arbiter** and mirrors its request/acknowledge semantics for the read-only subset. Preserves selected address and destinations for two output ports, mapped/unmapped decode and DECERR, registered downstream ARVALID/RREADY and upstream RVALID response-stalling behavior.
- Added a miter comparing multiple read-control signals rather than one AR acceptance event. RDATA deliberately excluded; S_RRESP included only when valid.
- Added seven formal proof scenarios, three non-vacuity/witness cover scenarios, and two deliberate negative-control mutations.
- Generated SBY tasks use original, unmodified upstream RTL and fail-closed classification; no text substitution in upstream source.
- Reproduced seven local source-grounded snapshot solver tests and fourteen offline regression tests. A true RTL equivalence result is *not* asserted until the independent GitHub SBY run succeeds.
