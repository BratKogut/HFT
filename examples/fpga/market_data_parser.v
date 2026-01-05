/**
 * Market Data Parser - FPGA Example (Verilog)
 * 
 * Educational example showing how FPGA parses incoming market data packets.
 * This is a SIMPLIFIED version for learning purposes.
 * 
 * Real HFT FPGA parsers are much more complex and handle:
 * - Multiple protocols (FIX, ITCH, OUCH, proprietary)
 * - Error correction
 * - Out-of-order packets
 * - Nanosecond timestamping
 * 
 * Latency: ~50-200 nanoseconds (real hardware)
 */

module market_data_parser (
    input wire clk,              // Clock (e.g., 200 MHz)
    input wire rst_n,            // Active-low reset
    
    // Input: Raw packet data
    input wire [63:0] packet_data,  // 64-bit data bus
    input wire packet_valid,         // Data valid signal
    
    // Output: Parsed market data
    output reg [31:0] symbol_id,     // Security ID
    output reg [63:0] price,         // Price (fixed-point)
    output reg [31:0] size,          // Order size
    output reg [7:0] side,           // 'B' = Buy, 'S' = Sell
    output reg data_ready            // Output valid signal
);

// State machine states
localparam IDLE = 2'b00;
localparam PARSE_HEADER = 2'b01;
localparam PARSE_BODY = 2'b10;
localparam DONE = 2'b11;

reg [1:0] state;
reg [7:0] msg_type;

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        state <= IDLE;
        symbol_id <= 32'b0;
        price <= 64'b0;
        size <= 32'b0;
        side <= 8'b0;
        data_ready <= 1'b0;
        msg_type <= 8'b0;
    end else begin
        case (state)
            IDLE: begin
                data_ready <= 1'b0;
                if (packet_valid) begin
                    // Extract message type from first byte
                    msg_type <= packet_data[7:0];
                    state <= PARSE_HEADER;
                end
            end
            
            PARSE_HEADER: begin
                // Parse header (symbol ID)
                symbol_id <= packet_data[31:0];
                state <= PARSE_BODY;
            end
            
            PARSE_BODY: begin
                // Parse body (price, size, side)
                price <= packet_data[63:32];  // Simplified: upper 32 bits = price
                size <= packet_data[31:16];   // Next 16 bits = size
                side <= packet_data[15:8];    // Next 8 bits = side
                
                data_ready <= 1'b1;  // Signal that data is ready
                state <= DONE;
            end
            
            DONE: begin
                data_ready <= 1'b0;
                state <= IDLE;
            end
            
            default: state <= IDLE;
        endcase
    end
end

endmodule

/**
 * USAGE NOTES:
 * 
 * 1. This is a SIMPLIFIED example. Real parsers handle:
 *    - Variable-length messages
 *    - Multiple message types (orders, trades, cancels)
 *    - Checksums and error detection
 *    - Timestamping with nanosecond precision
 * 
 * 2. Latency breakdown (real FPGA):
 *    - Packet arrival: 0 ns
 *    - Parse header: 5-10 ns
 *    - Parse body: 10-20 ns
 *    - Output ready: 50-100 ns
 *    - TOTAL: ~50-200 ns
 * 
 * 3. To synthesize for real FPGA:
 *    - Use Xilinx Vivado or Intel Quartus
 *    - Target: Xilinx Virtex UltraScale+ or Intel Stratix 10
 *    - Add timing constraints
 *    - Optimize for low latency (not area)
 * 
 * 4. Testing:
 *    - Use testbench (see market_data_parser_tb.v)
 *    - Simulate with ModelSim or Vivado Simulator
 *    - Verify timing with static timing analysis
 */
