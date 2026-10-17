// Real-RTL 2-master, SAME-destination, read-only AXI-Lite integration.
// RUN_MODE=0: cover both masters waiting AND each eventually completing.
// RUN_MODE=1: unbounded safety on the real upstream implementation.
// RUN_MODE=2: mutant response-routing safety (expected FAIL).
// RUN_MODE=3: mutant shutdown safety (expected FAIL).
`default_nettype none
module axi_shared_contention_formal_bench #(
    parameter RUN_MODE=0
)(
    input wire clk, rst,
    input wire [1:0] generate_read, consume_read, slave_stall,
    input wire shutdown_request
);
    wire [1:0] upstream_ar_accept,upstream_r_complete,waiting_ar;
    wire [1:0] internal_busy,request_dest,upstream_rvalid;
    wire [63:0] upstream_rdata;
    wire shutdown_latched,reconfig_start;
    axi_hetero_top #(
      .BAD_SHUTDOWN(RUN_MODE==3),
      .BAD_ROUTE(RUN_MODE==2),
      .USE_CONTRACT(0)
    ) dut(
      .clk(clk),.rst(rst),.generate_read(generate_read),
      .request_target(2'b00), // Both masters target physical slave zero.
      .consume_read(consume_read),.slave_stall(slave_stall),
      .shutdown_request(shutdown_request),
      .upstream_ar_accept(upstream_ar_accept),
      .upstream_r_complete(upstream_r_complete),
      .waiting_ar(waiting_ar),.internal_busy(internal_busy),
      .request_dest(request_dest),.upstream_rvalid(upstream_rvalid),
      .upstream_rdata(upstream_rdata),
      .shutdown_latched(shutdown_latched),.reconfig_start(reconfig_start)
    );
    reg initialized=0;
    reg saw_both_pending=0;
    reg saw_ar0=0,saw_ar1=0,saw_r0=0,saw_r1=0;
    reg [1:0] mon0=0,mon1=0;
    always @(posedge clk) begin
      initialized<=1;
      if (!initialized) assume(rst);
      else assume(!rst);
      if (RUN_MODE==0) begin
        assume(generate_read==2'b11);
        assume(consume_read==2'b11);
        assume(slave_stall==2'b00);
        assume(shutdown_request==1'b0);
      end
      if (rst) begin
        saw_both_pending<=0;
        saw_ar0<=0;saw_ar1<=0;saw_r0<=0;saw_r1<=0;
        mon0<=0;mon1<=0;
      end else begin
        if (waiting_ar==2'b11 && request_dest==2'b00) saw_both_pending<=1;
        if (upstream_ar_accept[0]) saw_ar0<=1;
        if (upstream_ar_accept[1]) saw_ar1<=1;
        if (upstream_r_complete[0]) saw_r0<=1;
        if (upstream_r_complete[1]) saw_r1<=1;
        case ({upstream_ar_accept[0],upstream_r_complete[0]})
          2'b10: mon0<=mon0+1'b1;
          2'b01: mon0<=mon0-1'b1;
          default: mon0<=mon0;
        endcase
        case ({upstream_ar_accept[1],upstream_r_complete[1]})
          2'b10: mon1<=mon1+1'b1;
          2'b01: mon1<=mon1-1'b1;
          default: mon1<=mon1;
        endcase
        if (RUN_MODE==0) begin
          cover(saw_both_pending && saw_ar0 && saw_ar1 && saw_r0 && saw_r1);
        end else begin
          assert(mon0 <= 1 && mon1 <= 1);
          if (upstream_r_complete[0]) assert(mon0!=0);
          if (upstream_r_complete[1]) assert(mon1!=0);
          assert(internal_busy[0] == (mon0!=0));
          assert(internal_busy[1] == (mon1!=0));
          assert(!(reconfig_start &&
                   (mon0!=0 || mon1!=0 || waiting_ar!=0)));
        end
      end
    end
endmodule
`default_nettype wire
