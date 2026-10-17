// Intent2Proof-authored, read-only AXI-Lite slave.
// The write channels are tied off at the integration boundary.
`default_nettype none
module axi_slow_read_slave #(
    parameter ADDR_WIDTH=16,
    parameter SLAVE_ID=0
)(
    input wire clk, input wire rst, input wire stall,
    input wire [ADDR_WIDTH-1:0] araddr,
    input wire arvalid, output wire arready,
    output reg [31:0] rdata,
    output wire [1:0] rresp,
    output reg rvalid, input wire rready
);
reg pending = 1'b0;
initial begin rvalid=0; rdata=0; end
assign arready = !pending && !rvalid;
assign rresp=2'b00;
always @(posedge clk) begin
  if(rst) begin
    pending <= 1'b0;
    rvalid <= 1'b0;
    rdata <= 32'b0;
  end else begin
    if (rvalid && rready)
      rvalid <= 1'b0;
    if (arvalid && arready) begin
      pending <= 1'b1;
      rdata <= 32'hA5000000 | (SLAVE_ID << 16) | araddr;
    end
    if (pending && !stall) begin
      pending <= 1'b0;
      rvalid <= 1'b1;
    end
  end
end
endmodule
`default_nettype wire
