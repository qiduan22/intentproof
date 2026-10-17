// Protocol-conforming follow-up to Intent2Proof AXI control contract v2.
// MODE: 0 arbitrary legal upstream traffic; 1/5 shared-slave one-shot;
// 2/8 distinct-slave one-shot; 3/7 unmapped one-shot; 4/6 mapped one-shot.
// CHECK_KIND: 0 prove control equivalence AND independent slave protocol;
// 1 cover complete legal transactions; 2 prove slave protocol ONLY (negative).
// CONTRACT_KIND: 0 corrected v2, 1 early-ready mutant, 2 drop-stall mutant.
// SLAVE_KIND: 0 legal, 1 intentionally unsolicited RVALID (negative control).
`default_nettype none
module axi_protocol_v3_formal_bench #(
    parameter MODE = 0,
    parameter CHECK_KIND = 0,
    parameter CONTRACT_KIND = 0,
    parameter SLAVE_KIND = 0
)(
    input wire clk, rst,
    input wire [1:0] stimulus_arvalid,
    input wire [31:0] stimulus_araddr,
    input wire [1:0] stimulus_rready,
    input wire [1:0] allow_slave_accept,
    input wire [1:0] allow_slave_respond
);
    reg past_valid = 1'b0;
    reg [1:0] issued = 2'b00;
    wire one_shot=(MODE!=0);
    wire [1:0] shot_mask=((MODE==3)||(MODE==4)||(MODE==6)||(MODE==7)) ? 2'b01 : 2'b11;
    wire [31:0] shot_addr = ((MODE==2)||(MODE==8)) ? 32'h0100_0000 :
                            ((MODE==3)||(MODE==7)) ? 32'h0000_0200 :
                            32'h0000_0000;
    wire [1:0] s_arvalid = rst ? 2'b00 :
                         (one_shot ? ((~issued) & shot_mask) : stimulus_arvalid);
    wire [31:0] s_araddr = one_shot ? shot_addr : stimulus_araddr;
    wire [1:0] s_rready = rst ? 2'b00 : stimulus_rready;
    wire [1:0] real_arready, abs_arready, real_rvalid, abs_rvalid;
    wire [1:0] real_m_arvalid, abs_m_arvalid, real_m_rready, abs_m_rready;
    wire [31:0] real_m_araddr, abs_m_araddr;
    wire [3:0] real_rresp, abs_rresp;
    wire [1:0] real_ar_accept, abs_ar_accept, real_r_complete, abs_r_complete;
    wire control_equal;
    wire [1:0] m_arready, m_rvalid;
    wire [63:0] m_rdata;
    wire [3:0] m_rresp;

    axi_read_control_miter_v2 #(.CONTRACT_KIND(CONTRACT_KIND)) miter(
        .clk(clk), .rst(rst), .s_arvalid(s_arvalid), .s_araddr(s_araddr),
        .s_rready(s_rready), .m_arready(m_arready), .m_rvalid(m_rvalid),
        .m_rdata(m_rdata), .m_rresp(m_rresp),
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

    // The slave responds to the ORIGINAL interconnect's downstream transfers,
    // not a DUT status flag. Both interconnect models see identical slave pins.
    // This is a *reference-driven* closed environment, not a proof of generic
    // independently composed AXI networks.
    axi_legal_read_slave_pair #(.INJECT_UNSOLICITED_RESPONSE(SLAVE_KIND)) slaves(
        .clk(clk), .rst(rst),
        .arvalid(real_m_arvalid), .araddr(real_m_araddr),
        .arready(m_arready), .rvalid(m_rvalid),
        .rready(real_m_rready), .rdata(m_rdata), .rresp(m_rresp),
        .allow_accept(allow_slave_accept), .allow_respond(allow_slave_respond)
    );

    wire [1:0] ds_ar_fire = real_m_arvalid & m_arready;
    wire [1:0] ds_r_fire = m_rvalid & real_m_rready;
    reg [1:0] monitor_pending = 2'b00;
    reg [2:0] accepted_slave0=3'b0, responded_slave0=3'b0;
    reg [2:0] accepted_slave1=3'b0, responded_slave1=3'b0;
    reg saw_both_requested=1'b0;
    reg [1:0] upstream_accepted=2'b0, upstream_completed=2'b0;
    reg last_cycle_stall=1'b0, saw_two_consecutive_stalls=1'b0;
    reg saw_unmapped_decerr=1'b0;

    always @(posedge clk) begin
      past_valid <= 1'b1;
      // Explicit, synchronous initial reset; subsequent cycles are out of reset.
      if (!past_valid) assume(rst);
      else assume(!rst);

      // Unconstrained master traffic is nevertheless AXI-stable while stalled.
      // One-shot sources automatically hold ARVALID/ARADDR until acceptance.
      if (past_valid && !$past(rst) && !rst && MODE==0) begin
        if ($past(s_arvalid[0] && !real_arready[0])) begin
          assume(s_arvalid[0]);
          assume(s_araddr[15:0]==$past(s_araddr[15:0]));
        end
        if ($past(s_arvalid[1] && !real_arready[1])) begin
          assume(s_arvalid[1]);
          assume(s_araddr[31:16]==$past(s_araddr[31:16]));
        end
      end
      if (rst) begin
        issued<=2'b00;
        monitor_pending<=2'b00;
        accepted_slave0<=0; responded_slave0<=0;
        accepted_slave1<=0; responded_slave1<=0;
        saw_both_requested<=0;
        upstream_accepted<=2'b00;
        upstream_completed<=2'b00;
        last_cycle_stall<=1'b0;
        saw_two_consecutive_stalls<=1'b0;
        saw_unmapped_decerr<=1'b0;
      end else begin
        issued <= issued | real_ar_accept;
        if (ds_ar_fire[0]) monitor_pending[0]<=1'b1;
        if (ds_ar_fire[1]) monitor_pending[1]<=1'b1;
        if (ds_r_fire[0]) monitor_pending[0]<=1'b0;
        if (ds_r_fire[1]) monitor_pending[1]<=1'b0;
        if (ds_ar_fire[0] && accepted_slave0<3) accepted_slave0<=accepted_slave0+1'b1;
        if (ds_r_fire[0] && responded_slave0<3) responded_slave0<=responded_slave0+1'b1;
        if (ds_ar_fire[1] && accepted_slave1<3) accepted_slave1<=accepted_slave1+1'b1;
        if (ds_r_fire[1] && responded_slave1<3) responded_slave1<=responded_slave1+1'b1;
        if (s_arvalid==2'b11 && s_araddr==32'h0000_0000)
          saw_both_requested<=1'b1;
        upstream_accepted<=upstream_accepted | real_ar_accept;
        upstream_completed<=upstream_completed | real_r_complete;
        if (last_cycle_stall && real_rvalid[0] && !s_rready[0])
          saw_two_consecutive_stalls<=1'b1;
        last_cycle_stall <= real_rvalid[0] && !s_rready[0];
        if (real_r_complete[0] && real_rresp[1:0]==2'b11)
          saw_unmapped_decerr<=1'b1;
      end

      if (past_valid && !rst) begin
        // Independent transaction scoreboard: any RVALID must follow an
        // actual downstream ARVALID && ARREADY event. Check each slave.
        assert(!m_rvalid[0] || monitor_pending[0]);
        assert(!m_rvalid[1] || monitor_pending[1]);
        assert(!(ds_ar_fire[0] && monitor_pending[0]));
        assert(!(ds_ar_fire[1] && monitor_pending[1]));
        assert(!(ds_r_fire[0] && !monitor_pending[0]));
        assert(!(ds_r_fire[1] && !monitor_pending[1]));
        if (!$past(rst)) begin
          if ($past(m_rvalid[0] && !real_m_rready[0])) begin
            assert(m_rvalid[0]);
            assert(m_rresp[1:0]==$past(m_rresp[1:0]));
            assert(m_rdata[31:0]==$past(m_rdata[31:0]));
          end
          if ($past(m_rvalid[1] && !real_m_rready[1])) begin
            assert(m_rvalid[1]);
            assert(m_rresp[3:2]==$past(m_rresp[3:2]));
            assert(m_rdata[63:32]==$past(m_rdata[63:32]));
          end
        end
        if (CHECK_KIND==0) begin
          assert(control_equal);
        end
        if (CHECK_KIND==1) begin
          if (MODE==5)
            cover(saw_both_requested && (&upstream_accepted) &&
                  (&upstream_completed) && accepted_slave0>=2 &&
                  responded_slave0>=2 && accepted_slave1==0);
          if (MODE==6)
            cover(saw_two_consecutive_stalls && upstream_completed[0] &&
                  accepted_slave0>=1 && responded_slave0>=1);
          if (MODE==7)
            cover(saw_unmapped_decerr && accepted_slave0==0 &&
                  accepted_slave1==0 && upstream_accepted[0]);
          if (MODE==8)
            cover((&upstream_completed) && accepted_slave0>=1 &&
                  accepted_slave1>=1 && responded_slave0>=1 &&
                  responded_slave1>=1);
        end
      end
    end
endmodule
`default_nettype wire
