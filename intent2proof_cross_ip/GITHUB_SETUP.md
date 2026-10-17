# Run cross-IP RTL verification on GitHub Actions

The previous pinned FIFO single-IP result is preserved. This is a **new** workflow using the same pinned upstream RTL source bundled in the package. It is independent of the earlier `intent2proof_upstream_validation` directory.

At the **GitHub repository root**, ensure the files look like:

```
.github/
  workflows/
    intent2proof-cross-ip.yml
intent2proof_cross_ip/
  rtl/
    sfifo.v
    fifo_control_contract.v
    cross_ip_top.v
  scripts/
    run_cross_ip.py
    gate_cross_ip.py
    plot_results.py
    ...
  tests/
    test_cross_ip.py
  results/
    model/
    composition/
  report/
    main.pdf
```

**Do not place `.github/workflows` inside `intent2proof_cross_ip/` only.** GitHub will not detect workflows nested under that project folder. If the upload dialog hides `.github`, go to your repository's **Code → Add file → Create new file**, type `.github/workflows/intent2proof-cross-ip.yml`, and paste the workflow YAML from the top-level folder of the ZIP.

Commit the project directory and workflow to the default branch. In **Actions**, choose **Intent2Proof cross-IP contract benchmark → Run workflow**. The workflow installs OSS CAD Suite, tests the Python generator, checks 18 RTL formal tasks, evaluates a fail-closed gate, and uploads an artifact named **`intent2proof-cross-ip-contract-sby`** even if some tasks fail.

Download and upload the complete artifact ZIP for analysis. Do not interpret a green GitHub check as proving more than the task-level evidence supports.
