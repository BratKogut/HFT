"""
Historical Data Downloader

Downloads historical market data from exchanges for backtesting:
- OHLCV candles
- Order book snapshots
- Trade history
- Multiple timeframes
"""

import asyncio
import ccxt.async_support as ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import os
import json


class HistoricalDataDownloader:
    """
    Download historical market data from exchanges
    
    Supports:
    - OHLCV data (1m, 5m, 1h, 1d)
    - Multiple symbols
    - Date range selection
    - Data caching
    """
    
    def __init__(self, exchange_name: str = 'binance', cache_dir: str = 'data/historical'):
        """
        Initialize data downloader
        
        Args:
            exchange_name: Exchange to download from
            cache_dir: Directory to cache downloaded data
        """
        self.exchange_name = exchange_name.lower()
        self.cache_dir = cache_dir
        self.exchange: Optional[ccxt.Exchange] = None
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
    
    async def initialize(self):
        """Initialize exchange connection"""
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
            self.exchange = exchange_class({
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'}
            })
            
            await self.exchange.load_markets()
            print(f"✅ Connected to {self.exchange_name.upper()} for data download")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            return False
    
    async def download_ohlcv(self,
                            symbol: str,
                            timeframe: str = '1m',
                            start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None,
                            limit: Optional[int] = None) -> pd.DataFrame:
        """
        Download OHLCV data
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe ('1m', '5m', '1h', '1d')
            start_date: Start date (if None, download last `limit` candles)
            end_date: End date (if None, use current time)
            limit: Max number of candles (if None, download all in date range)
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if not self.exchange:
            await self.initialize()
        
        # Check cache first
        cache_file = self._get_cache_filename(symbol, timeframe, start_date, end_date)
        if os.path.exists(cache_file):
            print(f"📁 Loading from cache: {cache_file}")
            df = pd.read_csv(cache_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        
        print(f"📥 Downloading {symbol} {timeframe} data...")
        
        all_candles = []
        
        if start_date and end_date:
            # Download by date range
            current_time = int(start_date.timestamp() * 1000)
            end_time = int(end_date.timestamp() * 1000)
            
            batch_size = 1000  # Max candles per request
            
            while current_time < end_time:
                try:
                    candles = await self.exchange.fetch_ohlcv(
                        symbol,
                        timeframe,
                        since=current_time,
                        limit=batch_size
                    )
                    
                    if not candles:
                        break
                    
                    all_candles.extend(candles)
                    
                    # Move to next batch
                    current_time = candles[-1][0] + 1
                    
                    print(f"   Downloaded {len(all_candles)} candles...", end='\r')
                    
                    # Rate limiting
                    await asyncio.sleep(self.exchange.rateLimit / 1000)
                    
                except Exception as e:
                    print(f"\n⚠️  Error downloading batch: {e}")
                    break
        
        else:
            # Download last N candles
            if limit is None:
                limit = 1000
            
            try:
                candles = await self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe,
                    limit=limit
                )
                all_candles = candles
                
            except Exception as e:
                print(f"❌ Failed to download: {e}")
                return pd.DataFrame()
        
        if not all_candles:
            print("\n❌ No data downloaded")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['timestamp']).reset_index(drop=True)
        
        print(f"\n✅ Downloaded {len(df)} candles")
        print(f"   Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        print(f"   Price range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
        
        # Cache the data
        df.to_csv(cache_file, index=False)
        print(f"💾 Cached to: {cache_file}")
        
        return df
    
    async def download_multiple_symbols(self,
                                       symbols: List[str],
                                       timeframe: str = '1m',
                                       days: int = 7) -> Dict[str, pd.DataFrame]:
        """
        Download data for multiple symbols
        
        Args:
            symbols: List of trading pairs
            timeframe: Candle timeframe
            days: Number of days to download
        
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        results = {}
        
        for symbol in symbols:
            print(f"\n{'='*80}")
            print(f"Downloading {symbol}...")
            print('='*80)
            
            df = await self.download_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            results[symbol] = df
        
        return results
    
    def _get_cache_filename(self,
                           symbol: str,
                           timeframe: str,
                           start_date: Optional[datetime],
                           end_date: Optional[datetime]) -> str:
        """Generate cache filename"""
        symbol_safe = symbol.replace('/', '_')
        
        if start_date and end_date:
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')
            filename = f"{symbol_safe}_{timeframe}_{start_str}_{end_str}.csv"
        else:
            filename = f"{symbol_safe}_{timeframe}_latest.csv"
        
        return os.path.join(self.cache_dir, filename)
    
    async def get_market_info(self, symbol: str) -> Dict:
        """Get market information for a symbol"""
        if not self.exchange:
            await self.initialize()
        
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            
            return {
                'symbol': symbol,
                'last_price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume_24h': ticker['quoteVolume'],
                'high_24h': ticker['high'],
                'low_24h': ticker['low'],
                'change_24h': ticker['percentage']
            }
            
        except Exception as e:
            print(f"❌ Failed to get market info: {e}")
            return {}
    
    async def close(self):
        """Close exchange connection"""
        if self.exchange:
            await self.exchange.close()


async def download_for_backtesting(symbols: List[str] = None,
                                   days: int = 30,
                                   timeframe: str = '1m'):
    """
    Convenient function to download data for backtesting
    
    Args:
        symbols: List of symbols (default: ['BTC/USDT', 'ETH/USDT'])
        days: Number of days to download
        timeframe: Candle timeframe
    """
    if symbols is None:
        symbols = ['BTC/USDT', 'ETH/USDT']
    
    downloader = HistoricalDataDownloader(exchange_name='binance')
    
    print("="*80)
    print("📥 HISTORICAL DATA DOWNLOADER")
    print("="*80)
    print(f"Exchange: Binance")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: Last {days} days")
    print("="*80)
    print()
    
    # Download data
    results = await downloader.download_multiple_symbols(
        symbols=symbols,
        timeframe=timeframe,
        days=days
    )
    
    # Summary
    print()
    print("="*80)
    print("📊 DOWNLOAD SUMMARY")
    print("="*80)
    
    for symbol, df in results.items():
        if not df.empty:
            print(f"\n{symbol}:")
            print(f"  Candles: {len(df)}")
            print(f"  Period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
            print(f"  Price: ${df['close'].iloc[-1]:,.2f}")
            print(f"  Range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
    
    await downloader.close()
    
    print()
    print("="*80)
    print("✅ DOWNLOAD COMPLETE")
    print("="*80)
    print(f"Data saved to: data/historical/")
    print()
    
    return results


# Example usage
if __name__ == "__main__":
    # Download 7 days of 1-minute data for BTC and ETH
    asyncio.run(download_for_backtesting(
        symbols=['BTC/USDT', 'ETH/USDT'],
        days=7,
        timeframe='1m'
    ))
