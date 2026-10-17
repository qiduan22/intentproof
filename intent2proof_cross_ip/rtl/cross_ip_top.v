// Three copies of pinned upstream ZipCPU sfifo plus custom round-robin merge
// and a fail-closed shutdown controller. Single clock; arbitrary backpressure.
// Reconfiguration safe only when *all* three FIFOs have drained.
module cross_ip_top #(
    parameter integer BW=8,
    parameter integer LGFLEN=2,
    parameter integer USE_CONTRACT=0,
    parameter integer BAD_SHUTDOWN=0
)(
    input wire clk, input wire reset,
    input wire wr_a, input wire wr_b, input wire rd_sink,
    input wire shutdown_request,
    input wire [BW-1:0] data_a, data_b,
    output wire [BW-1:0] payload_a, payload_b, payload_sink,
    output wire [LGFLEN:0] fill_a,fill_b,fill_sink,
    output wire empty_a,empty_b,empty_sink,
    output wire full_a,full_b,full_sink,
    output wire accepted_a,accepted_b,delivered,
    output wire take_a,take_b,write_sink,
    output reg shutdown_latched,
    output wire reconfig_start
);
    reg priority_b;
    initial begin priority_b = 0; shutdown_latched = 0; end
    wire request_a = wr_a && !shutdown_request && !shutdown_latched;
    wire request_b = wr_b && !shutdown_request && !shutdown_latched;
    assign accepted_a = request_a && !full_a;
    assign accepted_b = request_b && !full_b;

    wire pick_a = !empty_a && (empty_b || !priority_b);
    wire pick_b = !empty_b && (empty_a || priority_b);
    assign take_a = pick_a && !full_sink;
    assign take_b = pick_b && !full_sink;
    assign write_sink = take_a || take_b;
    assign delivered = rd_sink && !empty_sink;
    wire [BW-1:0] ingress_sink_data = take_a ? payload_a : payload_b;

    always @(posedge clk) begin
       if (reset) begin shutdown_latched<=0; priority_b<=0; end
       else begin
          if (shutdown_request) shutdown_latched<=1;
          if (write_sink) priority_b<=take_a;
       end
    end

    // Negative control: erroneously omit the sink FIFO's occupancy.
    assign reconfig_start = shutdown_latched && empty_a && empty_b
                         && ((BAD_SHUTDOWN != 0) ? 1'b1 : empty_sink);

    generate if (USE_CONTRACT != 0) begin : ABSTRACT
       fifo_control_contract #(.BW(BW),.LGFLEN(LGFLEN)) qa (
         .i_clk(clk), .i_reset(reset), .i_wr(request_a), .i_data(data_a),
         .o_full(full_a),.o_fill(fill_a),.i_rd(take_a),.o_data(payload_a),.o_empty(empty_a));
       fifo_control_contract #(.BW(BW),.LGFLEN(LGFLEN)) qb (
         .i_clk(clk), .i_reset(reset), .i_wr(request_b), .i_data(data_b),
         .o_full(full_b),.o_fill(fill_b),.i_rd(take_b),.o_data(payload_b),.o_empty(empty_b));
       fifo_control_contract #(.BW(BW),.LGFLEN(LGFLEN)) qs (
         .i_clk(clk), .i_reset(reset), .i_wr(write_sink), .i_data(ingress_sink_data),
         .o_full(full_sink),.o_fill(fill_sink),.i_rd(rd_sink),.o_data(payload_sink),.o_empty(empty_sink));
    end else begin : CONCRETE
       sfifo #(.BW(BW),.LGFLEN(LGFLEN),.OPT_ASYNC_READ(1'b1),
           .OPT_WRITE_ON_FULL(1'b0),.OPT_READ_ON_EMPTY(1'b0)) qa (
         .i_clk(clk),.i_reset(reset),.i_wr(request_a),.i_data(data_a),
         .o_full(full_a),.o_fill(fill_a),.i_rd(take_a),.o_data(payload_a),.o_empty(empty_a));
       sfifo #(.BW(BW),.LGFLEN(LGFLEN),.OPT_ASYNC_READ(1'b1),
           .OPT_WRITE_ON_FULL(1'b0),.OPT_READ_ON_EMPTY(1'b0)) qb (
         .i_clk(clk),.i_reset(reset),.i_wr(request_b),.i_data(data_b),
         .o_full(full_b),.o_fill(fill_b),.i_rd(take_b),.o_data(payload_b),.o_empty(empty_b));
       sfifo #(.BW(BW),.LGFLEN(LGFLEN),.OPT_ASYNC_READ(1'b1),
           .OPT_WRITE_ON_FULL(1'b0),.OPT_READ_ON_EMPTY(1'b0)) qs (
         .i_clk(clk),.i_reset(reset),.i_wr(write_sink),.i_data(ingress_sink_data),
         .o_full(full_sink),.o_fill(fill_sink),.i_rd(rd_sink),.o_data(payload_sink),.o_empty(empty_sink));
    end endgenerate
endmodule
