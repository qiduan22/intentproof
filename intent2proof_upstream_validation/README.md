# Intent2Proof upstream-RTL validation harness (repaired)

See `../RUN_THIS.md` for setup and execution, or `CURRENT_EXECUTION_STATUS.md` for the exact current results and limitations. The benchmark targets upstream ZipCPU `rtl/sfifo.v`, pins a commit and source hash, then checks three FIFO sizes with full, COI, candidate control-equivalence, deliberate mutant, and cover tasks.

**No full RTL verification was run in the ChatGPT container** because Yosys/SBY/Z3 CLI and Github access were unavailable. All seven offline harness tests passed. Github Actions workflow is supplied, but not executed.
