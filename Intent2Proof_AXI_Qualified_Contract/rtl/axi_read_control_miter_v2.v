// v2 cycle-accurate control-observation miter against pinned upstream Verilog.
// Restricted to READ-ONLY AXI-Lite with 2 sources/2 destinations and
// explicit map 0x0000/0x0100, region width 8. Contract does not model RDATA.
`default_nettype none
module axi_read_control_miter_v2 #(
    parameter CONTRACT_KIND=0 // 0=correct,1=early_ready_mutant,2=drop_stalled_response_mutant
)(
    input wire clk,rst,
    input wire [1:0] s_arvalid,
    input wire [31:0] s_araddr,
    input wire [1:0] s_rready,
    input wire [1:0] m_arready,
    input wire [1:0] m_rvalid,
    input wire [63:0] m_rdata,
    input wire [3:0] m_rresp,
    output wire [1:0] real_arready, abs_arready,
    output wire [1:0] real_rvalid, abs_rvalid,
    output wire [1:0] real_m_arvalid, abs_m_arvalid,
    output wire [1:0] real_m_rready, abs_m_rready,
    output wire [31:0] real_m_araddr, abs_m_araddr,
    output wire [3:0] real_rresp, abs_rresp,
    output wire [1:0] real_ar_accept, abs_ar_accept,
    output wire [1:0] real_r_complete, abs_r_complete,
    output wire control_equal
);
    wire [1:0] real_s_awready, real_s_wready, real_s_bvalid;
    wire [3:0] real_s_bresp;
    wire [1:0] real_m_awvalid,real_m_wvalid,real_m_bready;
    wire [31:0] real_m_awaddr;
    wire [5:0] real_m_awprot,real_m_arprot;
    wire [63:0] real_m_wdata;
    wire [7:0] real_m_wstrb;
    wire [63:0] real_s_rdata;
    wire [3:0] real_s_rresp;
    wire [1:0] real_s_arready;
    wire [1:0] real_m_rready_i;
    wire [31:0] real_m_araddr_i;
    wire [1:0] real_m_arvalid_i;
    wire [1:0] real_s_rvalid_i;

    axil_interconnect #(
        .S_COUNT(2), .M_COUNT(2), .DATA_WIDTH(32), .ADDR_WIDTH(16),
        .M_REGIONS(1), .M_BASE_ADDR({16'h0100,16'h0000}),
        .M_ADDR_WIDTH({32'd8,32'd8})
    ) real_ip (
        .clk(clk),.rst(rst),
        .s_axil_awaddr(32'b0),.s_axil_awprot(6'b0),
        .s_axil_awvalid(2'b0),.s_axil_awready(real_s_awready),
        .s_axil_wdata(64'b0),.s_axil_wstrb(8'b0),
        .s_axil_wvalid(2'b0),.s_axil_wready(real_s_wready),
        .s_axil_bresp(real_s_bresp),.s_axil_bvalid(real_s_bvalid),
        .s_axil_bready(2'b11),
        .s_axil_araddr(s_araddr),.s_axil_arprot(6'b0),
        .s_axil_arvalid(s_arvalid),.s_axil_arready(real_s_arready),
        .s_axil_rdata(real_s_rdata),.s_axil_rresp(real_s_rresp),
        .s_axil_rvalid(real_s_rvalid_i),.s_axil_rready(s_rready),
        .m_axil_awaddr(real_m_awaddr),.m_axil_awprot(real_m_awprot),
        .m_axil_awvalid(real_m_awvalid),.m_axil_awready(2'b00),
        .m_axil_wdata(real_m_wdata),.m_axil_wstrb(real_m_wstrb),
        .m_axil_wvalid(real_m_wvalid),.m_axil_wready(2'b00),
        .m_axil_bresp(4'b0),.m_axil_bvalid(2'b00),
        .m_axil_bready(real_m_bready),
        .m_axil_araddr(real_m_araddr_i),.m_axil_arprot(real_m_arprot),
        .m_axil_arvalid(real_m_arvalid_i),.m_axil_arready(m_arready),
        .m_axil_rdata(m_rdata),.m_axil_rresp(m_rresp),
        .m_axil_rvalid(m_rvalid),.m_axil_rready(real_m_rready_i)
    );
    wire [1:0] ctr_arready,ctr_rvalid,ctr_m_arvalid,ctr_m_rready;
    wire [31:0] ctr_m_araddr;
    wire [3:0] ctr_rresp;

    generate
      if (CONTRACT_KIND==0) begin: normal
        axi_read_control_contract_v2 abstract_ip (
           .clk(clk),.rst(rst),.s_arvalid(s_arvalid),.s_arready(ctr_arready),
           .s_araddr(s_araddr),.s_rvalid(ctr_rvalid),.s_rready(s_rready),
           .s_rresp(ctr_rresp),.m_arvalid(ctr_m_arvalid),.m_arready(m_arready),
           .m_araddr(ctr_m_araddr),.m_rvalid(m_rvalid),.m_rready(ctr_m_rready),
           .m_rresp(m_rresp)
        );
      end else if (CONTRACT_KIND==1) begin: early_ready
        axi_read_control_contract_v2_early_ready abstract_ip (
           .clk(clk),.rst(rst),.s_arvalid(s_arvalid),.s_arready(ctr_arready),
           .s_araddr(s_araddr),.s_rvalid(ctr_rvalid),.s_rready(s_rready),
           .s_rresp(ctr_rresp),.m_arvalid(ctr_m_arvalid),.m_arready(m_arready),
           .m_araddr(ctr_m_araddr),.m_rvalid(m_rvalid),.m_rready(ctr_m_rready),
           .m_rresp(m_rresp)
        );
      end else begin: lost_response
        axi_read_control_contract_v2_drop_stalled_response abstract_ip (
           .clk(clk),.rst(rst),.s_arvalid(s_arvalid),.s_arready(ctr_arready),
           .s_araddr(s_araddr),.s_rvalid(ctr_rvalid),.s_rready(s_rready),
           .s_rresp(ctr_rresp),.m_arvalid(ctr_m_arvalid),.m_arready(m_arready),
           .m_araddr(ctr_m_araddr),.m_rvalid(m_rvalid),.m_rready(ctr_m_rready),
           .m_rresp(m_rresp)
        );
      end
    endgenerate

    assign real_arready=real_s_arready;
    assign abs_arready=ctr_arready;
    assign real_rvalid=real_s_rvalid_i;
    assign abs_rvalid=ctr_rvalid;
    assign real_m_arvalid=real_m_arvalid_i;
    assign abs_m_arvalid=ctr_m_arvalid;
    assign real_m_rready=real_m_rready_i;
    assign abs_m_rready=ctr_m_rready;
    assign real_m_araddr=real_m_araddr_i;
    assign abs_m_araddr=ctr_m_araddr;
    assign real_rresp=real_s_rresp;
    assign abs_rresp=ctr_rresp;
    assign real_ar_accept=s_arvalid & real_arready;
    assign abs_ar_accept=s_arvalid & abs_arready;
    assign real_r_complete=real_rvalid & s_rready;
    assign abs_r_complete=abs_rvalid & s_rready;

    // Payload data is deliberately excluded from this control-only contract.
    // Compare address and RESP only in protocol-valid observation windows.
    assign control_equal=
      (real_arready==abs_arready) &&
      (real_rvalid==abs_rvalid) &&
      (real_m_arvalid==abs_m_arvalid) &&
      (real_m_rready==abs_m_rready) &&
      ((|(real_m_arvalid|abs_m_arvalid)) ?
          (real_m_araddr==abs_m_araddr) : 1'b1) &&
      ((|(real_rvalid|abs_rvalid)) ?
          (real_rresp==abs_rresp) : 1'b1);
endmodule
`default_nettype wire
