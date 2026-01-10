"""
HFT MVP Tier 1 - Configuration Management
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Exchange Configuration
    exchange_api_key: str = Field(default="", env="EXCHANGE_API_KEY")
    exchange_api_secret: str = Field(default="", env="EXCHANGE_API_SECRET")
    exchange_name: str = Field(default="binance", env="EXCHANGE_NAME")
    
    # Trading Configuration
    trading_mode: Literal["paper", "shadow", "live"] = Field(default="paper", env="TRADING_MODE")
    trading_pair: str = Field(default="BTC/USDT", env="TRADING_PAIR")
    base_capital: float = Field(default=10000.0, env="BASE_CAPITAL")
    max_position_size: float = Field(default=1000.0, env="MAX_POSITION_SIZE")
    max_risk_per_trade: float = Field(default=0.02, env="MAX_RISK_PER_TRADE")
    
    # Database
    mongodb_uri: str = Field(default="mongodb://localhost:27017", env="MONGODB_URI")
    mongodb_db: str = Field(default="hft_mvp", env="MONGODB_DB")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    
    # Server
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    ws_port: int = Field(default=8001, env="WS_PORT")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/hft_mvp.log", env="LOG_FILE")
    
    # Monitoring
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
