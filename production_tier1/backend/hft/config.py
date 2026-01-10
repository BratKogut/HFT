"""
Configuration Management
========================

Pydantic-based configuration for HFT system.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
from decimal import Decimal


class ExchangeConfig(BaseSettings):
    """Exchange configuration."""
    
    name: str = "binance"
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    
    # Rate limiting
    requests_per_second: int = 10
    orders_per_second: int = 5
    
    class Config:
        env_prefix = "EXCHANGE_"


class TradingConfig(BaseSettings):
    """Trading configuration."""
    
    # Trading mode
    mode: str = "paper"  # paper, shadow, live
    
    # Symbols to trade
    symbols: List[str] = ["BTCUSDT", "ETHUSDT"]
    
    # Position sizing
    max_position_size: Decimal = Decimal("1.0")
    default_order_size: Decimal = Decimal("0.01")
    
    # Leverage
    leverage: int = 1
    
    class Config:
        env_prefix = "TRADING_"


class RiskConfig(BaseSettings):
    """Risk management configuration."""
    
    # Position limits
    max_positions: int = 5
    max_position_value_usd: Decimal = Decimal("10000")
    
    # Order limits
    max_order_size: Decimal = Decimal("1.0")
    max_order_value_usd: Decimal = Decimal("5000")
    
    # Loss limits
    max_daily_loss_usd: Decimal = Decimal("1000")
    max_drawdown_percent: Decimal = Decimal("10")
    
    # Price collars
    max_price_deviation_percent: Decimal = Decimal("5")
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_loss_threshold: Decimal = Decimal("500")
    
    class Config:
        env_prefix = "RISK_"


class StrategyConfig(BaseSettings):
    """Strategy configuration."""
    
    # Active strategies
    active_strategies: List[str] = ["market_making"]
    
    # Market making
    mm_spread_bps: int = 10  # basis points
    mm_order_size: Decimal = Decimal("0.01")
    mm_max_inventory: Decimal = Decimal("1.0")
    
    # Momentum
    momentum_lookback: int = 20
    momentum_threshold: Decimal = Decimal("0.02")
    
    # Mean reversion
    mr_lookback: int = 50
    mr_std_dev: Decimal = Decimal("2.0")
    
    class Config:
        env_prefix = "STRATEGY_"


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "hft_production"
    
    class Config:
        env_prefix = "DB_"


class MonitoringConfig(BaseSettings):
    """Monitoring configuration."""
    
    # Latency thresholds (milliseconds)
    latency_warning_ms: int = 50
    latency_critical_ms: int = 100
    
    # Performance metrics
    metrics_interval_seconds: int = 60
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "hft_production.log"
    
    class Config:
        env_prefix = "MONITORING_"


class Config(BaseSettings):
    """Main configuration."""
    
    # Sub-configurations
    exchange: ExchangeConfig = ExchangeConfig()
    trading: TradingConfig = TradingConfig()
    risk: RiskConfig = RiskConfig()
    strategy: StrategyConfig = StrategyConfig()
    database: DatabaseConfig = DatabaseConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Environment
    environment: str = "development"  # development, staging, production
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global config instance
config = Config()
