// Formal benchmark for cycle-accurate control-observation comparison.
// MODE is parameterized by the benchmark runner:
// 0: arbitrary legal-ish read requests + response/backpressure (prove)
// 1: master0 to slave0 only (prove)
// 2: both masters to same slave0 (prove)
// 3: both masters to distinct slaves (prove)
// 4: unmapped address (prove)
// 5: requests and response stalls (prove)
// 6: resets may recur after initial reset (prove)
// 7: two-master contention and two completed responses (cover)
// 8: response held under upstream backpressure (cover)
// 9: unmapped read emits DECERR (cover)
// CONTRACT_KIND=0 correct, 1 early-ready mutant, 2 lost-response mutant.
`default_nettype none
module axi_refinement_v2_formal_bench #(
    parameter MODE=0,
    parameter CONTRACT_KIND=0,
    parameter CHECK_KIND=0 // 0 assertion, 1 cover
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
    wire [1:0] real_arready, abs_arready;
    wire [1:0] real_rvalid, abs_rvalid;
    wire [1:0] real_m_arvalid, abs_m_arvalid;
    wire [1:0] real_m_rready, abs_m_rready;
    wire [31:0] real_m_araddr, abs_m_araddr;
    wire [3:0] real_rresp, abs_rresp;
    wire [1:0] real_ar_accept, abs_ar_accept;
    wire [1:0] real_r_complete, abs_r_complete;
    wire control_equal;

    axi_read_control_miter_v2 #(.CONTRACT_KIND(CONTRACT_KIND)) dut(
        .clk(clk),.rst(rst),.s_arvalid(s_arvalid),.s_araddr(s_araddr),
        .s_rready(s_rready),.m_arready(m_arready),.m_rvalid(m_rvalid),
        .m_rdata(m_rdata),.m_rresp(m_rresp),
        .real_arready(real_arready),.abs_arready(abs_arready),
        .real_rvalid(real_rvalid),.abs_rvalid(abs_rvalid),
        .real_m_arvalid(real_m_arvalid),.abs_m_arvalid(abs_m_arvalid),
        .real_m_rready(real_m_rready),.abs_m_rready(abs_m_rready),
        .real_m_araddr(real_m_araddr),.abs_m_araddr(abs_m_araddr),
        .real_rresp(real_rresp),.abs_rresp(abs_rresp),
        .real_ar_accept(real_ar_accept),.abs_ar_accept(abs_ar_accept),
        .real_r_complete(real_r_complete),.abs_r_complete(abs_r_complete),
        .control_equal(control_equal)
    );

    reg have_past=1'b0;
    reg saw_dual=1'b0;
    reg saw_accept0=1'b0,saw_accept1=1'b0;
    reg saw_complete0=1'b0,saw_complete1=1'b0;
    reg saw_response_stall=1'b0;
    reg saw_held_response=1'b0;
    reg saw_unmapped_decerr=1'b0;

    always @(posedge clk) begin
      have_past<=1'b1;
      if (!have_past) begin
        assume(rst);
        assume(s_arvalid==2'b00);
      end else if (MODE!=6) begin
        assume(!rst);
      end

      // No read requests are admitted during reset.
      if (rst) begin
        assume(s_arvalid==2'b00);
        assume(m_rvalid==2'b00);
      end

      // Master's AXI-Lite ARVALID/ARADDR stability until handshake.
      // Applies to both constrained and unconstrained request traffic.
      if (have_past && !$past(rst) && !rst) begin
        if ($past(s_arvalid[0] && !real_arready[0])) begin
          assume(s_arvalid[0]);
          assume(s_araddr[15:0]==$past(s_araddr[15:0]));
        end
        if ($past(s_arvalid[1] && !real_arready[1])) begin
          assume(s_arvalid[1]);
          assume(s_araddr[31:16]==$past(s_araddr[31:16]));
        end
        // Slave responses remain valid and stable while stalled.
        if ($past(m_rvalid[0] && !real_m_rready[0])) begin
          assume(m_rvalid[0]);
          assume(m_rresp[1:0]==$past(m_rresp[1:0]));
          assume(m_rdata[31:0]==$past(m_rdata[31:0]));
        end
        if ($past(m_rvalid[1] && !real_m_rready[1])) begin
          assume(m_rvalid[1]);
          assume(m_rresp[3:2]==$past(m_rresp[3:2]));
          assume(m_rdata[63:32]==$past(m_rdata[63:32]));
        end
      end
      if (have_past && !rst) begin
        if (MODE==1) begin
          assume(s_arvalid==2'b01);
          assume(s_araddr==32'h0000_0000);
        end
        if (MODE==2 || MODE==7) begin
          assume(s_arvalid==2'b11);
          assume(s_araddr==32'h0000_0000);
        end
        if (MODE==3) begin
          assume(s_arvalid==2'b11);
          assume(s_araddr==32'h0100_0000);
        end
        if (MODE==4 || MODE==9) begin
          assume(s_arvalid==2'b01);
          assume(s_araddr==32'h0000_0200);
        end
        if (MODE==5) begin
          // No artificial speed assumption; all ready/valid stalls allowed.
          // Restrict source only to master0 mapped to slave0.
          assume(s_arvalid==2'b01);
          assume(s_araddr==32'h0000_0000);
        end
        if (MODE==8) begin
          assume(s_arvalid==2'b01);
          assume(s_araddr==32'h0000_0000);
        end
      end

      if (rst) begin
        saw_dual<=0;
        saw_accept0<=0; saw_accept1<=0;
        saw_complete0<=0; saw_complete1<=0;
        saw_response_stall<=0;
        saw_held_response<=0;
        saw_unmapped_decerr<=0;
      end else begin
        if (s_arvalid==2'b11 && s_araddr[15:0]==16'h0000 &&
            s_araddr[31:16]==16'h0000)
          saw_dual<=1'b1;
        if (real_ar_accept[0]) saw_accept0<=1'b1;
        if (real_ar_accept[1]) saw_accept1<=1'b1;
        if (real_r_complete[0]) saw_complete0<=1'b1;
        if (real_r_complete[1]) saw_complete1<=1'b1;
        if (|(real_rvalid & ~s_rready)) saw_response_stall<=1'b1;
        if (saw_response_stall && (|(real_rvalid & ~s_rready)))
          saw_held_response<=1'b1;
        if ((|(real_rvalid & s_rready)) && real_rresp==4'b1111)
          saw_unmapped_decerr<=1'b1;
      end

      if (have_past && !rst) begin
        if (CHECK_KIND==0)
          assert(control_equal);
        else if (MODE==7)
          cover(saw_dual && saw_accept0 && saw_accept1 &&
                saw_complete0 && saw_complete1);
        else if (MODE==8)
          cover(saw_held_response && (|real_r_complete));
        else if (MODE==9)
          cover(saw_unmapped_decerr);
      end
    end
endmodule
`default_nettype wire
