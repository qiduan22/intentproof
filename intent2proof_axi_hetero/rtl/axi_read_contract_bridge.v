// Intent2Proof candidate single-outstanding AXI-Lite read bridge abstraction.
// NOT claimed to be a verified refinement of the upstream AXI-Lite interconnect.
`default_nettype none
module axi_read_contract_bridge(
 input wire clk, rst,
 input wire [1:0] s_arvalid,
 output wire [1:0] s_arready,
 input wire [31:0] s_araddr,
 output wire [1:0] s_rvalid,
 input wire [1:0] s_rready,
 output wire [63:0] s_rdata,
 output wire [3:0] s_rresp,
 output wire [1:0] m_arvalid,
 input wire [1:0] m_arready,
 output wire [31:0] m_araddr,
 input wire [1:0] m_rvalid,
 output wire [1:0] m_rready,
 input wire [63:0] m_rdata,
 input wire [3:0] m_rresp
);
 reg [1:0] state=0; // 0 idle, 1 downstream address, 2 downstream response
 reg owner=0,dest=0,turn=0;
 initial begin owner=0;dest=0;turn=0;end
 wire chosen=(s_arvalid[turn] ? turn : !turn);
 wire active=s_arvalid[0]||s_arvalid[1];
 assign s_arready=(state==0 && active) ? (chosen ? 2'b10:2'b01):2'b00;
 assign m_arvalid=(state==1) ? (dest ? 2'b10:2'b01):2'b00;
 assign m_araddr={2{dest ? 16'h0100:16'h0000}};
 assign m_rready=(state==2 && s_rready[owner]) ? (dest ? 2'b10:2'b01):2'b00;
 assign s_rvalid=(state==2 && m_rvalid[dest]) ? (owner ? 2'b10:2'b01):2'b00;
 assign s_rdata={2{m_rdata[dest*32+:32]}};
 assign s_rresp={2{m_rresp[dest*2+:2]}};
 always @(posedge clk) begin
   if(rst) begin state<=0;owner<=0;dest<=0;turn<=0;end
   else if(state==0 && active) begin
     owner<=chosen;
     dest<=s_araddr[chosen*16+8];
     turn<=~chosen;
     state<=1;
   end else if(state==1 && m_arready[dest]) state<=2;
   else if(state==2 && m_rvalid[dest] && s_rready[owner]) state<=0;
 end
endmodule
`default_nettype wire
