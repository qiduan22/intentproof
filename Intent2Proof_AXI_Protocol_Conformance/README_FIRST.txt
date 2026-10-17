Intent2Proof AXI legal-slave protocol refinement v3

This experiment fixes the v2 verification-environment issue: read responses
could be supplied before any downstream read-address acceptance.

1. Upload Intent2Proof_AXI_Protocol_Conformance/ to the root of your GitHub repo.
2. Place the provided workflow at repository-root
   .github/workflows/intent2proof-axi-protocol-v3.yml
3. Commit and launch a NEW GitHub Actions workflow run:
   "Intent2Proof AXI v3 legal-transaction refinement".
4. Download artifact "intent2proof-axi-v3-legal-transaction-evidence" and
   upload it to ChatGPT for an actual proof and waveform audit.

LOCAL RESULTS: 18/18 offline tests pass; the Python reference model explores
3 states for one slave and 9 for two. These ARE NOT upstream RTL proofs.
The environment here lacks Yosys/SBY/Z3, so full-RTL proofs are NOT RUN.

See docs/ASSUMPTIONS.md and EVALUATION_REPORT.md before claiming anything.
