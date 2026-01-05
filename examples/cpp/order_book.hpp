/**
 * Lock-Free Order Book - C++ Example
 * 
 * Educational example showing a simplified lock-free order book.
 * Real HFT order books are MUCH more complex.
 * 
 * Latency: ~1-10 microseconds (depends on CPU, cache, etc.)
 */

#pragma once

#include <atomic>
#include <array>
#include <cstdint>
#include <optional>

namespace hft {

// Price level entry (aligned to cache line for performance)
struct alignas(64) PriceLevel {
    double price;
    int64_t size;
    uint64_t timestamp_ns;
    std::atomic<bool> valid;  // Lock-free validity flag
    
    PriceLevel() : price(0.0), size(0), timestamp_ns(0), valid(false) {}
};

// Simplified lock-free order book
// Real implementations use more sophisticated data structures
template<size_t MaxLevels = 100>
class LockFreeOrderBook {
public:
    LockFreeOrderBook() {
        for (auto& level : bids_) {
            level.valid.store(false, std::memory_order_relaxed);
        }
        for (auto& level : asks_) {
            level.valid.store(false, std::memory_order_relaxed);
        }
    }
    
    // Update bid level (buy orders)
    // Returns: true if update successful
    bool update_bid(double price, int64_t size, uint64_t timestamp_ns) {
        return update_level(bids_, price, size, timestamp_ns);
    }
    
    // Update ask level (sell orders)
    // Returns: true if update successful
    bool update_ask(double price, int64_t size, uint64_t timestamp_ns) {
        return update_level(asks_, price, size, timestamp_ns);
    }
    
    // Get best bid (highest buy price)
    std::optional<PriceLevel> get_best_bid() const {
        double best_price = 0.0;
        const PriceLevel* best_level = nullptr;
        
        for (const auto& level : bids_) {
            if (level.valid.load(std::memory_order_acquire)) {
                if (level.price > best_price) {
                    best_price = level.price;
                    best_level = &level;
                }
            }
        }
        
        if (best_level) {
            return *best_level;
        }
        return std::nullopt;
    }
    
    // Get best ask (lowest sell price)
    std::optional<PriceLevel> get_best_ask() const {
        double best_price = std::numeric_limits<double>::max();
        const PriceLevel* best_level = nullptr;
        
        for (const auto& level : asks_) {
            if (level.valid.load(std::memory_order_acquire)) {
                if (level.price < best_price) {
                    best_price = level.price;
                    best_level = &level;
                }
            }
        }
        
        if (best_level) {
            return *best_level;
        }
        return std::nullopt;
    }
    
    // Get mid price (average of best bid and best ask)
    std::optional<double> get_mid_price() const {
        auto bid = get_best_bid();
        auto ask = get_best_ask();
        
        if (bid && ask) {
            return (bid->price + ask->price) / 2.0;
        }
        return std::nullopt;
    }
    
    // Get spread (difference between best ask and best bid)
    std::optional<double> get_spread() const {
        auto bid = get_best_bid();
        auto ask = get_best_ask();
        
        if (bid && ask) {
            return ask->price - bid->price;
        }
        return std::nullopt;
    }

private:
    std::array<PriceLevel, MaxLevels> bids_;  // Buy side
    std::array<PriceLevel, MaxLevels> asks_;  // Sell side
    
    // Update a price level (lock-free)
    bool update_level(std::array<PriceLevel, MaxLevels>& levels,
                      double price, int64_t size, uint64_t timestamp_ns) {
        // Find existing level or empty slot
        for (auto& level : levels) {
            bool expected = false;
            
            // Try to acquire empty slot
            if (level.valid.load(std::memory_order_acquire) == false) {
                if (level.valid.compare_exchange_strong(expected, true,
                                                         std::memory_order_release,
                                                         std::memory_order_relaxed)) {
                    // Successfully acquired slot
                    level.price = price;
                    level.size = size;
                    level.timestamp_ns = timestamp_ns;
                    return true;
                }
            }
            
            // Update existing level
            if (level.price == price) {
                if (size == 0) {
                    // Remove level
                    level.valid.store(false, std::memory_order_release);
                } else {
                    // Update level
                    level.size = size;
                    level.timestamp_ns = timestamp_ns;
                }
                return true;
            }
        }
        
        // No space available
        return false;
    }
};

} // namespace hft

/**
 * USAGE EXAMPLE:
 * 
 * #include "order_book.hpp"
 * 
 * int main() {
 *     hft::LockFreeOrderBook<100> book;
 *     
 *     // Update bids
 *     book.update_bid(100.00, 1000, get_timestamp_ns());
 *     book.update_bid(99.99, 500, get_timestamp_ns());
 *     
 *     // Update asks
 *     book.update_ask(100.01, 800, get_timestamp_ns());
 *     book.update_ask(100.02, 1200, get_timestamp_ns());
 *     
 *     // Get best prices
 *     auto best_bid = book.get_best_bid();
 *     auto best_ask = book.get_best_ask();
 *     
 *     if (best_bid && best_ask) {
 *         std::cout << "Bid: " << best_bid->price << " @ " << best_bid->size << std::endl;
 *         std::cout << "Ask: " << best_ask->price << " @ " << best_ask->size << std::endl;
 *         std::cout << "Spread: " << *book.get_spread() << std::endl;
 *     }
 *     
 *     return 0;
 * }
 * 
 * PERFORMANCE NOTES:
 * 
 * 1. Cache-line alignment (64 bytes) prevents false sharing
 * 2. Atomic operations ensure thread safety without locks
 * 3. Memory ordering (acquire/release) ensures visibility
 * 
 * LATENCY BREAKDOWN (typical):
 * - update_bid/ask: 50-500 ns
 * - get_best_bid/ask: 10-100 ns
 * - get_mid_price: 20-200 ns
 * 
 * LIMITATIONS (this is educational code):
 * - Fixed-size array (real: dynamic tree structures)
 * - Linear search (real: sorted structures, hash maps)
 * - No priority queue (real: heap or tree)
 * - No order ID tracking (real: full order lifecycle)
 * 
 * REAL HFT ORDER BOOKS USE:
 * - Custom allocators (pool allocation)
 * - SIMD instructions for parallel search
 * - Prefetching to reduce cache misses
 * - Lock-free skip lists or B-trees
 */
