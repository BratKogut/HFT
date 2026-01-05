"""Configuration Management"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os

class Settings(BaseSettings):
    """HFT System Settings"""
    
    # MongoDB
    mongo_url: str = Field(default="mongodb://localhost:27017")
    mongo_db: str = Field(default="hft_system")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379")
    
    # Exchange
    exchange_mode: str = Field(default="simulator")  # simulator | live
    exchange_api_key: str = Field(default="")
    exchange_api_secret: str = Field(default="")
    
    # Trading
    default_symbol: str = Field(default="BTC/USD")
    default_timeframe: str = Field(default="1m")
    
    # Risk Management
    max_position_size: float = Field(default=10.0)
    max_order_size: float = Field(default=1.0)
    daily_loss_limit: float = Field(default=1000.0)
    price_collar_pct: float = Field(default=0.05)  # 5%
    
    # Strategy
    market_making_spread: float = Field(default=0.001)  # 0.1%
    market_making_size: float = Field(default=0.1)
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    
    # CORS
    allowed_origins: List[str] = Field(default=["http://localhost:3000"])
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
