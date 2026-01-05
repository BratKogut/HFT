"""Market Data Handler - Async market data processing"""

import asyncio
from typing import Optional
from hft.exchange_simulator import ExchangeSimulator
from hft.order_book import OrderBook
from hft.latency_monitor import LatencyMonitor
from hft.strategy_engine import StrategyEngine

class MarketDataHandler:
    """Handle market data ingestion and processing"""
    
    def __init__(self, settings, strategy_engine: StrategyEngine, latency_monitor: LatencyMonitor):
        self.settings = settings
        self.strategy_engine = strategy_engine
        self.latency_monitor = latency_monitor
        
        self.exchange_simulator: Optional[ExchangeSimulator] = None
        self.order_book: Optional[OrderBook] = None
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self, symbol: str):
        """Start market data feed"""
        if self.is_running:
            print("⚠️  Market data already running")
            return
        
        print(f"📊 Starting market data for {symbol}...")
        
        # Initialize order book
        self.order_book = OrderBook(symbol)
        
        # Initialize exchange (simulator or real)
        if self.settings.exchange_mode == "simulator":
            self.exchange_simulator = ExchangeSimulator(symbol)
            await self.exchange_simulator.start()
        else:
            # TODO: Connect to real exchange
            raise NotImplementedError("Real exchange connection not implemented yet")
        
        self.is_running = True
        
        # Start market data loop
        self._task = asyncio.create_task(self._market_data_loop())
        
        print(f"✅ Market data started for {symbol}")
    
    async def stop(self):
        """Stop market data feed"""
        if not self.is_running:
            return
        
        print("🛑 Stopping market data...")
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self.exchange_simulator:
            await self.exchange_simulator.stop()
        
        print("✅ Market data stopped")
    
    async def _market_data_loop(self):
        """Main market data processing loop"""
        try:
            while self.is_running:
                start_time = self.latency_monitor.start_timer()
                
                # Get market data tick
                tick = await self.exchange_simulator.get_tick()
                
                # Record market data latency
                self.latency_monitor.record("market_data", start_time)
                
                # Update order book
                self.order_book.update(tick["bids"], tick["asks"])
                
                # Process through strategy engine
                await self.strategy_engine.on_market_data(self.order_book, tick)
                
                # Sleep for update interval (simulate real market data rate)
                await asyncio.sleep(0.01)  # 100 Hz = 10ms updates
                
        except asyncio.CancelledError:
            print("🛑 Market data loop cancelled")
        except Exception as e:
            print(f"❌ Error in market data loop: {e}")
            self.is_running = False
    
    def get_order_book(self) -> dict:
        """Get current order book snapshot"""
        if self.order_book:
            return self.order_book.get_snapshot()
        return {"error": "Order book not initialized"}
    
    def get_current_price(self) -> float:
        """Get current mid price"""
        if self.order_book:
            return self.order_book.get_mid_price()
        return 0.0
