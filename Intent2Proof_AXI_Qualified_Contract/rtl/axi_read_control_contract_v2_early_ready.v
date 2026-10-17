// NEGATIVE CONTROL: deliberately faulty contract, never use for approval.
// Intent2Proof v2: scope-restricted, READ-ONLY, TWO-source/TWO-destination
// interface-control projection of alexforencich/verilog-axi axil_interconnect.
// This is a manually authored contract candidate, NOT a qualified abstraction
// until the attached miter has proved the declared output relation.
//
// Observables: S_ARREADY, S_RVALID, S_RRESP (when valid), M_ARVALID,
// M_ARADDR (when valid), M_RREADY. Payload RDATA is deliberately *not*
// modeled or claimed; arbitrary safety properties using RDATA are unsupported.
//
// The original arbiter is instantiated to preserve grant/ack semantics.
// Only the original read path, address decode, and registered handshakes remain.
// Instantiation must tie all AXI-Lite write request inputs low.
`default_nettype none
module axi_read_control_contract_v2_early_ready (
    input wire clk, rst,
    input wire [1:0] s_arvalid,
    output wire [1:0] s_arready,
    input wire [31:0] s_araddr,
    output wire [1:0] s_rvalid,
    input wire [1:0] s_rready,
    output wire [3:0] s_rresp,
    output wire [1:0] m_arvalid,
    input wire [1:0] m_arready,
    output wire [31:0] m_araddr,
    input wire [1:0] m_rvalid,
    output wire [1:0] m_rready,
    input wire [3:0] m_rresp
);
    localparam [2:0] ST_IDLE=3'd0, ST_DECODE=3'd1,
        ST_READ=3'd5, ST_WAIT=3'd6;

    reg [2:0] state_reg=ST_IDLE, state_next;
    reg [1:0] s_arready_reg=2'b00, s_arready_next;
    reg [1:0] s_rvalid_reg=2'b00, s_rvalid_next;
    reg [1:0] m_arvalid_reg=2'b00, m_arvalid_next;
    reg [1:0] m_rready_reg=2'b00, m_rready_next;
    reg [15:0] addr_reg=16'b0, addr_next;
    reg addr_valid_reg=1'b0, addr_valid_next;
    reg m_select_reg=1'b0, m_select_next;
    reg [1:0] resp_reg=2'b00, resp_next;

    wire [3:0] request;
    wire [3:0] acknowledge;
    wire [3:0] grant;
    wire grant_valid;
    wire [1:0] grant_encoded;
    wire selected_slave=grant_encoded[1];
    wire [15:0] chosen_addr=s_araddr[selected_slave*16 +: 16];
    wire [1:0] chosen_resp=m_rresp[m_select_reg*2 +: 2];
    wire chosen_m_rready=m_rready_reg[m_select_reg];
    wire chosen_m_rvalid=m_rvalid[m_select_reg];
    wire decoded_ok=(addr_reg[15:8]==8'h00)||(addr_reg[15:8]==8'h01);
    wire decoded_dest=(addr_reg[15:8]==8'h01);

    assign request = {s_arvalid[1],1'b0,s_arvalid[0],1'b0};
    assign acknowledge = {
        grant[3] && s_rvalid_reg[1] && s_rready[1],
        1'b0,
        grant[1] && s_rvalid_reg[0] && s_rready[0],
        1'b0
    };
    arbiter #(
        .PORTS(4), .ARB_TYPE_ROUND_ROBIN(1),
        .ARB_BLOCK(1), .ARB_BLOCK_ACK(1), .ARB_LSB_HIGH_PRIORITY(1)
    ) read_arbiter (
        .clk(clk), .rst(rst), .request(request),
        .acknowledge(acknowledge), .grant(grant),
        .grant_valid(grant_valid), .grant_encoded(grant_encoded)
    );

    assign s_arready=(state_reg==ST_IDLE && (|s_arvalid)) ? (s_arvalid[0] ? 2'b01 : 2'b10) : s_arready_reg;
    assign s_rvalid=s_rvalid_reg;
    assign s_rresp={2{resp_reg}};
    assign m_arvalid=m_arvalid_reg;
    assign m_araddr={2{addr_reg}};
    assign m_rready=m_rready_reg;

    always @* begin
        state_next=ST_IDLE;
        s_arready_next=2'b00;
        s_rvalid_next=s_rvalid_reg & ~s_rready;
        m_arvalid_next=m_arvalid_reg & ~m_arready;
        m_rready_next=2'b00;
        addr_next=addr_reg;
        addr_valid_next=addr_valid_reg;
        m_select_next=m_select_reg;
        resp_next=resp_reg;
        case (state_reg)
            ST_IDLE: begin
                if (grant_valid) begin
                    addr_valid_next=1'b1;
                    addr_next=chosen_addr;
                    s_arready_next[selected_slave]=1'b1;
                    state_next=ST_DECODE;
                end
            end
            ST_DECODE: begin
                if (decoded_ok) begin
                    m_select_next=decoded_dest;
                    m_rready_next[decoded_dest]=1'b1;
                    state_next=ST_READ;
                end else begin
                    resp_next=2'b11; // AXI DECERR on unmapped address
                    s_rvalid_next[selected_slave]=1'b1;
                    state_next=ST_WAIT;
                end
            end
            ST_READ: begin
                m_rready_next[m_select_reg]=1'b1;
                if (addr_valid_reg) m_arvalid_next[m_select_reg]=1'b1;
                addr_valid_next=1'b0;
                if (chosen_m_rready && chosen_m_rvalid) begin
                    m_rready_next[m_select_reg]=1'b0;
                    resp_next=chosen_resp;
                    s_rvalid_next[selected_slave]=1'b1;
                    state_next=ST_WAIT;
                end else begin
                    state_next=ST_READ;
                end
            end
            ST_WAIT: begin
                if (!grant_valid || (|acknowledge))
                    state_next=ST_IDLE;
                else
                    state_next=ST_WAIT;
            end
            default: state_next=ST_IDLE;
        endcase
    end

    always @(posedge clk) begin
        if (rst) begin
            state_reg<=ST_IDLE;
            s_arready_reg<=2'b00;
            s_rvalid_reg<=2'b00;
            m_arvalid_reg<=2'b00;
            m_rready_reg<=2'b00;
        end else begin
            state_reg<=state_next;
            s_arready_reg<=s_arready_next;
            s_rvalid_reg<=s_rvalid_next;
            m_arvalid_reg<=m_arvalid_next;
            m_rready_reg<=m_rready_next;
        end
        // Mirrors the source's data/control-register reset semantics:
        // these registers are initialized but not separately reset here.
        addr_reg<=addr_next;
        addr_valid_reg<=addr_valid_next;
        m_select_reg<=m_select_next;
        resp_reg<=resp_next;
    end
endmodule
`default_nettype wire
