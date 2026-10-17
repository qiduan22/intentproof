// Count-only contract model for ZipCPU sfifo with the fixed options below.
// Do not substitute unless the independently proven contract obligation passes
// for the identical RTL SHA, parameters, initialization and reset semantics.
// NOTE: The payload output is intentionally unconstrained for data-aware checks;
// this module must ONLY be used for the listed control-only properties.
module fifo_control_contract #(
    parameter integer BW=8,
    parameter integer LGFLEN=2
)(
    input wire i_clk, input wire i_reset,
    input wire i_wr, input wire [BW-1:0] i_data,
    output wire o_full, output reg [LGFLEN:0] o_fill,
    input wire i_rd, output wire [BW-1:0] o_data, output wire o_empty
);
    localparam [LGFLEN:0] DEPTH = (1 << LGFLEN);
    initial o_fill = 0;
    assign o_full = (o_fill == DEPTH);
    assign o_empty = (o_fill == 0);
    // Payload not modeled. Any payload-dependent property is OUT OF SCOPE.
    assign o_data = {BW{1'b0}};
    wire take_write = i_wr && !o_full;
    wire take_read  = i_rd && !o_empty;
    always @(posedge i_clk) begin
        if (i_reset)
            o_fill <= 0;
        else
            case ({take_write, take_read})
                2'b10: o_fill <= o_fill + 1'b1;
                2'b01: o_fill <= o_fill - 1'b1;
                default: begin end
            endcase
    end
endmodule
