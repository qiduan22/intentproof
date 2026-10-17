// Independent formal harness. RUN_MODE is set by the per-task SBY config:
// 0: lockstep equivalence test (expected FAIL)
// 1: no-requests sanity invariant (expected PASS)
// 2: explicit mismatch cover (expected COVERED)
`default_nettype none
module axi_refinement_formal_bench #(
    parameter RUN_MODE=0,
    parameter DUAL_REQUEST=0
)(
    input wire clk, rst,
    input wire [1:0] s_arvalid,
    input wire [31:0] s_araddr,
    input wire [1:0] s_rready,
    input wire [1:0] m_arready,
    input wire [1:0] m_rvalid,
    input wire [63:0] m_rdata,
    input wire [3:0] m_rresp
);
    wire [1:0] r_acc,a_acc,r_done,a_done,r_valid,a_valid,r_down,a_down;
    wire [1:0] r_ready,a_ready;
    axi_read_bridge_miter dut(
      .clk(clk),.rst(rst),.s_arvalid(s_arvalid),
      .s_araddr(s_araddr),.s_rready(s_rready),
      .m_arready(m_arready),.m_rvalid(m_rvalid),
      .m_rdata(m_rdata),.m_rresp(m_rresp),
      .real_arready(r_ready),.contract_arready(a_ready),
      .real_ar_accept(r_acc),.contract_ar_accept(a_acc),
      .real_r_complete(r_done),.contract_r_complete(a_done),
      .real_rvalid(r_valid),.contract_rvalid(a_valid),
      .real_m_arvalid(r_down),.contract_m_arvalid(a_down)
    );
    reg initialized=1'b0;
    always @(posedge clk) begin
      initialized <= 1'b1;
      // AXI requires master ARVALID to be low while reset is asserted.
      if (!initialized) begin
        assume(rst);
        assume(s_arvalid==2'b00);
      end else begin
        assume(!rst);
        if (RUN_MODE==1) assume(s_arvalid==2'b00);
        else if (DUAL_REQUEST!=0) assume(s_arvalid==2'b11);
        else assume(s_arvalid==2'b01);
      end
      // Isolate the observable AR acceptance mismatch from downstream responses.
      assume(m_rvalid==2'b00);
      assume(m_arready==2'b00);
      assume(s_rready==2'b11);
      assume(s_araddr==32'b0);
      if (initialized && !rst) begin
        if (RUN_MODE==0)
          assert(r_acc == a_acc);
        else if (RUN_MODE==1) begin
          assert(r_acc==0);
          assert(a_acc==0);
          assert(r_ready==0);
          assert(a_ready==0);
        end else if (RUN_MODE==2)
          cover(r_acc != a_acc);
      end
    end
endmodule
`default_nettype wire
