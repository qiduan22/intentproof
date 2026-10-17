// Intent2Proof-authored heterogeneous read-only AXI-Lite integration.
// Real upstream interconnect module axil_interconnect and arbiter are
// obtained at the recorded Git revision by the reproducibility runner.
`default_nettype none
module axi_hetero_top #(
    parameter BAD_SHUTDOWN=0,
    parameter BAD_ROUTE=0,
    parameter USE_CONTRACT=0
)(
    input wire clk, input wire rst,
    input wire [1:0] generate_read,
    input wire [1:0] request_target,
    input wire [1:0] consume_read,
    input wire [1:0] slave_stall,
    input wire shutdown_request,
    output wire [1:0] upstream_ar_accept,
    output wire [1:0] upstream_r_complete,
    output wire [1:0] waiting_ar,
    output wire [1:0] internal_busy,
    output wire [1:0] request_dest,
    output wire [1:0] upstream_rvalid,
    output wire [63:0] upstream_rdata,
    output wire shutdown_latched,
    output wire reconfig_start
);
  reg [1:0] ar_hold=2'b00;
  reg [1:0] busy=2'b00;
  reg [1:0] dest_bit=2'b00;
  reg shdn=1'b0;
  wire [1:0] s_arready,s_rvalid;
  wire [63:0] s_rdata;
  wire [1:0] s_rresp;
  wire [1:0] ar_accepted=ar_hold&s_arready;
  // An injected wiring mutation incorrectly swaps both read-response channels.
  // Actual interconnect RREADY follows the miswired consumer in mutant mode.
  wire [1:0] delivered_rvalid = BAD_ROUTE ? {s_rvalid[0],s_rvalid[1]} : s_rvalid;
  wire [1:0] interconnect_rready = BAD_ROUTE ? {consume_read[0],consume_read[1]} : consume_read;
  wire [1:0] r_completed = delivered_rvalid & consume_read;
  wire [1:0] m_arvalid,m_arready,m_rvalid,m_rready;
  wire [31:0] m_araddr;
  wire [5:0] m_arprot;
  wire [63:0] m_rdata;
  wire [3:0] m_rresp;
  wire [1:0] m_awvalid,m_wvalid,m_bready;
  wire [31:0] m_awaddr;
  wire [5:0] m_awprot;
  wire [63:0] m_wdata;
  wire [7:0] m_wstrb;
  wire [1:0] s_awready,s_wready,s_bvalid;
  wire [3:0] s_bresp;

  assign upstream_ar_accept=ar_accepted;
  assign upstream_r_complete=r_completed;
  assign waiting_ar=ar_hold;
  assign internal_busy=busy;
  assign request_dest=dest_bit;
  assign upstream_rvalid=delivered_rvalid;
  assign upstream_rdata=BAD_ROUTE ? {s_rdata[31:0],s_rdata[63:32]} : s_rdata;
  assign shutdown_latched=shdn;
  assign reconfig_start=shdn &&
        ((BAD_SHUTDOWN != 0) ? (!ar_hold[0] && !busy[0])
                              : (ar_hold==2'b00 && busy==2'b00));
  wire [31:0] s_araddr={dest_bit[1] ? 16'h0100 : 16'h0000,
                         dest_bit[0] ? 16'h0100 : 16'h0000};
  always @(posedge clk) begin
    if(rst) begin
      ar_hold<=0;busy<=0;dest_bit<=0;shdn<=0;
    end else begin
      if(shutdown_request) shdn<=1'b1;
      // Each master holds ARVALID until ARREADY; at most one outstanding read.
      // New requests stop at a shutdown request, but requests already presented
      // to AXI remain valid until accepted (AXI ready/valid stability).
      if(!shdn && !shutdown_request) begin
        if(!ar_hold[0] && !busy[0] && generate_read[0]) begin
           ar_hold[0]<=1;dest_bit[0]<=request_target[0];
        end
        if(!ar_hold[1] && !busy[1] && generate_read[1]) begin
           ar_hold[1]<=1;dest_bit[1]<=request_target[1];
        end
      end
      if(ar_accepted[0]) begin ar_hold[0]<=0;busy[0]<=1;end
      if(ar_accepted[1]) begin ar_hold[1]<=0;busy[1]<=1;end
      if(r_completed[0]) busy[0]<=0;
      if(r_completed[1]) busy[1]<=0;
    end
  end

  // The dedicated contract abstraction is a candidate to be qualified; its
  // trace inclusion is NOT assumed or claimed by the benchmark gate.
  generate if(USE_CONTRACT) begin: abstract_bridge
     axi_read_contract_bridge bridge(
       .clk(clk),.rst(rst),.s_arvalid(ar_hold),.s_arready(s_arready),
       .s_araddr(s_araddr),.s_rvalid(s_rvalid),.s_rready(interconnect_rready),
       .s_rdata(s_rdata),.s_rresp(s_rresp),.m_arvalid(m_arvalid),
       .m_arready(m_arready),.m_araddr(m_araddr),.m_rvalid(m_rvalid),
       .m_rready(m_rready),.m_rdata(m_rdata),.m_rresp(m_rresp));
     assign m_arprot=0;
     assign m_awvalid=0; assign m_wvalid=0;assign m_bready=0;
     assign m_awaddr=0; assign m_awprot=0;
     assign m_wdata=0; assign m_wstrb=0;
     assign s_awready=0; assign s_wready=0;
     assign s_bvalid=0; assign s_bresp=0;
  end else begin: upstream_bridge
     axil_interconnect #(
       .S_COUNT(2),.M_COUNT(2),.DATA_WIDTH(32),.ADDR_WIDTH(16),
       .M_REGIONS(1),.M_BASE_ADDR({16'h0100,16'h0000}),
       .M_ADDR_WIDTH({32'd8,32'd8})
     ) upstream (
       .clk(clk),.rst(rst),
       .s_axil_awaddr(32'b0),.s_axil_awprot(6'b0),
       .s_axil_awvalid(2'b0),.s_axil_awready(s_awready),
       .s_axil_wdata(64'b0),.s_axil_wstrb(8'b0),
       .s_axil_wvalid(2'b0),.s_axil_wready(s_wready),
       .s_axil_bresp(s_bresp),.s_axil_bvalid(s_bvalid),
       .s_axil_bready(2'b11),
       .s_axil_araddr(s_araddr),.s_axil_arprot(6'b0),
       .s_axil_arvalid(ar_hold),.s_axil_arready(s_arready),
       .s_axil_rdata(s_rdata),.s_axil_rresp(s_rresp),
       .s_axil_rvalid(s_rvalid),.s_axil_rready(interconnect_rready),
       .m_axil_awaddr(m_awaddr),.m_axil_awprot(m_awprot),
       .m_axil_awvalid(m_awvalid),.m_axil_awready(2'b00),
       .m_axil_wdata(m_wdata),.m_axil_wstrb(m_wstrb),
       .m_axil_wvalid(m_wvalid),.m_axil_wready(2'b00),
       .m_axil_bresp(4'b0),.m_axil_bvalid(2'b00),
       .m_axil_bready(m_bready),
       .m_axil_araddr(m_araddr),.m_axil_arprot(m_arprot),
       .m_axil_arvalid(m_arvalid),.m_axil_arready(m_arready),
       .m_axil_rdata(m_rdata),.m_axil_rresp(m_rresp),
       .m_axil_rvalid(m_rvalid),.m_axil_rready(m_rready)
     );
  end endgenerate
  genvar k;
  generate for(k=0;k<2;k=k+1) begin: slaves
    axi_slow_read_slave #(.ADDR_WIDTH(16),.SLAVE_ID(k)) slave(
       .clk(clk),.rst(rst),.stall(slave_stall[k]),
       .araddr(m_araddr[k*16+:16]),
       .arvalid(m_arvalid[k]),.arready(m_arready[k]),
       .rdata(m_rdata[k*32+:32]),
       .rresp(m_rresp[k*2+:2]),
       .rvalid(m_rvalid[k]),.rready(m_rready[k])
    );
  end endgenerate
endmodule
`default_nettype wire
