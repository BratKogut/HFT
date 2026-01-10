"""
HFT MVP Tier 1 - Market Data Handler
Real-time market data via WebSocket
"""

import asyncio
import ccxt.pro as ccxtpro
from typing import Dict, Callable, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketDataHandler:
    """Real-time market data handler using WebSocket"""
    
    def __init__(self, exchange_name: str, api_key: str = "", api_secret: str = ""):
        """
        Initialize market data handler
        
        Args:
            exchange_name: Exchange name (e.g., 'binance')
            api_key: API key (optional for public data)
            api_secret: API secret (optional for public data)
        """
        self.exchange_name = exchange_name
        self.exchange = None
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Callbacks
        self.ticker_callbacks = []
        self.orderbook_callbacks = []
        self.trade_callbacks = []
        
        # State
        self.is_running = False
        self.subscribed_symbols = set()
        
        logger.info(f"MarketDataHandler initialized for {exchange_name}")
    
    async def connect(self):
        """Connect to exchange WebSocket"""
        try:
            exchange_class = getattr(ccxtpro, self.exchange_name)
            self.exchange = exchange_class({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'enableRateLimit': True,
            })
            
            logger.info(f"Connected to {self.exchange_name} WebSocket")
            self.is_running = True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.exchange_name}: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from exchange WebSocket"""
        if self.exchange:
            await self.exchange.close()
            self.is_running = False
            logger.info(f"Disconnected from {self.exchange_name}")
    
    def register_ticker_callback(self, callback: Callable):
        """Register callback for ticker updates"""
        self.ticker_callbacks.append(callback)
    
    def register_orderbook_callback(self, callback: Callable):
        """Register callback for orderbook updates"""
        self.orderbook_callbacks.append(callback)
    
    def register_trade_callback(self, callback: Callable):
        """Register callback for trade updates"""
        self.trade_callbacks.append(callback)
    
    async def subscribe_ticker(self, symbol: str):
        """
        Subscribe to ticker updates
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
        """
        if not self.exchange:
            raise RuntimeError("Not connected to exchange")
        
        self.subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to ticker: {symbol}")
        
        try:
            while self.is_running:
                ticker = await self.exchange.watch_ticker(symbol)
                
                # Add timestamp
                ticker['timestamp_received'] = datetime.utcnow().isoformat()
                
                # Notify callbacks
                for callback in self.ticker_callbacks:
                    try:
                        await callback(ticker)
                    except Exception as e:
                        logger.error(f"Ticker callback error: {e}")
                
        except Exception as e:
            logger.error(f"Error in ticker subscription for {symbol}: {e}")
    
    async def subscribe_orderbook(self, symbol: str, limit: int = 20):
        """
        Subscribe to orderbook updates
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            limit: Number of levels (default: 20)
        """
        if not self.exchange:
            raise RuntimeError("Not connected to exchange")
        
        self.subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to orderbook: {symbol}")
        
        try:
            while self.is_running:
                orderbook = await self.exchange.watch_order_book(symbol, limit)
                
                # Add timestamp and calculate spread
                orderbook['timestamp_received'] = datetime.utcnow().isoformat()
                if orderbook['bids'] and orderbook['asks']:
                    best_bid = orderbook['bids'][0][0]
                    best_ask = orderbook['asks'][0][0]
                    orderbook['spread'] = best_ask - best_bid
                    orderbook['spread_pct'] = (orderbook['spread'] / best_bid) * 100
                
                # Notify callbacks
                for callback in self.orderbook_callbacks:
                    try:
                        await callback(orderbook)
                    except Exception as e:
                        logger.error(f"Orderbook callback error: {e}")
                
        except Exception as e:
            logger.error(f"Error in orderbook subscription for {symbol}: {e}")
    
    async def subscribe_trades(self, symbol: str):
        """
        Subscribe to trade updates
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
        """
        if not self.exchange:
            raise RuntimeError("Not connected to exchange")
        
        self.subscribed_symbols.add(symbol)
        logger.info(f"Subscribed to trades: {symbol}")
        
        try:
            while self.is_running:
                trades = await self.exchange.watch_trades(symbol)
                
                # Add timestamp
                for trade in trades:
                    trade['timestamp_received'] = datetime.utcnow().isoformat()
                
                # Notify callbacks
                for callback in self.trade_callbacks:
                    try:
                        await callback(trades)
                    except Exception as e:
                        logger.error(f"Trade callback error: {e}")
                
        except Exception as e:
            logger.error(f"Error in trades subscription for {symbol}: {e}")
    
    async def get_ticker(self, symbol: str) -> Dict:
        """
        Get current ticker (REST API fallback)
        
        Args:
            symbol: Trading pair
            
        Returns:
            Ticker data
        """
        if not self.exchange:
            raise RuntimeError("Not connected to exchange")
        
        return await self.exchange.fetch_ticker(symbol)
    
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """
        Get current orderbook (REST API fallback)
        
        Args:
            symbol: Trading pair
            limit: Number of levels
            
        Returns:
            Orderbook data
        """
        if not self.exchange:
            raise RuntimeError("Not connected to exchange")
        
        return await self.exchange.fetch_order_book(symbol, limit)


# Example usage
async def main():
    """Example usage of MarketDataHandler"""
    
    # Create handler
    handler = MarketDataHandler('binance')
    
    # Register callbacks
    async def on_ticker(ticker):
        print(f"Ticker: {ticker['symbol']} - Last: {ticker['last']}")
    
    async def on_orderbook(orderbook):
        print(f"Orderbook: {orderbook['symbol']} - Spread: {orderbook.get('spread', 0):.2f}")
    
    handler.register_ticker_callback(on_ticker)
    handler.register_orderbook_callback(on_orderbook)
    
    # Connect and subscribe
    await handler.connect()
    
    # Run subscriptions concurrently
    await asyncio.gather(
        handler.subscribe_ticker('BTC/USDT'),
        handler.subscribe_orderbook('BTC/USDT'),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
