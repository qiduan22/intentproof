# Upload and run in qiduan22/intentproof

1. Upload `Intent2Proof_AXI_Qualified_Contract` to the repository root, with its `rtl`, `scripts`, `tests`, `third_party`, `results/local`, and `docs` directories.
2. Under the repository **Code** tab, select **Add file → Create new file**.
3. For filename enter `.github/workflows/intent2proof-axi-contract-v2.yml` and paste the separate workflow file from the ZIP. Commit on `main` (or the default branch).
4. From **Actions**, select **Intent2Proof AXI contract v2 refinement**, click **Run workflow**, choose the updated branch, and start a NEW run.
5. Under the successful run **Summary**, download artifact `intent2proof-axi-control-v2-evidence`. Upload that ZIP for independent audit.

Do not confuse the script's 14 offline tests or the seven local one-step Z3 results with the twelve actual SBY tasks. The artifacts must contain individual SBY statuses, proof logs, AIG models and violation/cover VCDs. On a failed run, the workflow still uploads partial evidence.
