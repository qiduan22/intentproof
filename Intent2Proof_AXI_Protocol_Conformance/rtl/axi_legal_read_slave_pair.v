// Intent2Proof v3: two AXI-Lite read-only responder models.
// Legal variant: each slave accepts at most one AR transaction; responses
// are registered, originate exclusively from accepted addresses, and remain
// stable while RVALID && !RREADY. No liveness or response deadline assumed.
// Parameters allow an intentionally ILLEGAL unsolicited-response mutation
// for validating the independent protocol monitor.
// The legal responder supports arbitrary delays and backpressure via
// allow_accept / allow_respond nondeterministic formal inputs.
`default_nettype none
module axi_legal_read_slave_pair #(
    parameter INJECT_UNSOLICITED_RESPONSE = 0
)(
    input wire clk, rst,
    input wire [1:0] arvalid,
    input wire [31:0] araddr,
    output wire [1:0] arready,
    output wire [1:0] rvalid,
    input wire [1:0] rready,
    output wire [63:0] rdata,
    output wire [3:0] rresp,
    input wire [1:0] allow_accept,
    input wire [1:0] allow_respond
);
    reg [1:0] pending = 2'b00;
    reg [1:0] rvalid_reg = 2'b00;
    reg [31:0] data0 = 32'b0, data1 = 32'b0;
    reg [3:0] status = 4'b0;

    assign arready = (~pending) & allow_accept & {2{!rst}};
    // Fault injection is solely a negative control, not a valid AXI model.
    assign rvalid = rvalid_reg | ((INJECT_UNSOLICITED_RESPONSE != 0) ?
        {1'b0, (!rst && !pending[0])} : 2'b00);
    assign rdata = {data1, data0};
    assign rresp = status;

    always @(posedge clk) begin
      if (rst) begin
        pending <= 2'b00;
        rvalid_reg <= 2'b00;
        data0 <= 32'b0;
        data1 <= 32'b0;
        status <= 4'b0;
      end else begin
        // Each slave has a one-transaction outstanding capacity.
        if (arvalid[0] && arready[0]) begin
          pending[0] <= 1'b1;
          // The payload pattern is retained but is outside the miter.
          data0 <= {16'hA510, araddr[15:0]};
          status[1:0] <= 2'b00; // OKAY
        end
        if (arvalid[1] && arready[1]) begin
          pending[1] <= 1'b1;
          data1 <= {16'hB620, araddr[31:16]};
          status[3:2] <= 2'b00;
        end
        if (pending[0] && !rvalid_reg[0] && allow_respond[0])
          rvalid_reg[0] <= 1'b1;
        if (pending[1] && !rvalid_reg[1] && allow_respond[1])
          rvalid_reg[1] <= 1'b1;
        if (rvalid_reg[0] && rready[0]) begin
          rvalid_reg[0] <= 1'b0;
          pending[0] <= 1'b0;
        end
        if (rvalid_reg[1] && rready[1]) begin
          rvalid_reg[1] <= 1'b0;
          pending[1] <= 1'b0;
        end
      end
    end
endmodule
`default_nettype wire
