# GitHub setup

1. Extract the ZIP at the **root** of https://github.com/qiduan22/intentproof.
2. It must contain the folder `Intent2Proof_AXI_Protocol_Conformance/`.
3. Put the workflow in repository-root
   `.github/workflows/intent2proof-axi-protocol-v3.yml`. If `.github` is
   hidden by the uploader, use GitHub **Add file -> Create new file** with
   that exact filename and paste the supplied YAML content.
4. Commit the new files to the branch you will run (e.g. `main`).
5. Open **Actions -> Intent2Proof AXI v3 legal-transaction refinement ->
   Run workflow** and choose the updated branch. Start a NEW workflow run,
   not "Re-run jobs" on a historical commit.
6. Download the Actions artifact
   `intent2proof-axi-v3-legal-transaction-evidence` and upload the ZIP here.

The run contains 12 tasks (5 PDR safety proofs, 4 transaction-aware covers,
3 negative controls). The gate will fail if any expected status is missing,
an unexpected failure occurs, a cover cannot be reached, or a mutant does
not produce a concrete witness. Analyze `RUN_STATUS.json`, `task_results.csv`,
`*.log`, and VCD/SMTC waveforms, not only the GitHub green check.
