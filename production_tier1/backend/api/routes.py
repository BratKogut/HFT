"""
API Routes with OpenAPI Documentation
=====================================

FastAPI routes with full OpenAPI/Swagger documentation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field


# ====================
# Enums for API
# ====================

class OrderSideEnum(str, Enum):
    """Order side enumeration."""
    buy = "buy"
    sell = "sell"


class OrderTypeEnum(str, Enum):
    """Order type enumeration."""
    market = "market"
    limit = "limit"


class TradingModeEnum(str, Enum):
    """Trading mode enumeration."""
    simulated = "simulated"
    sandbox = "sandbox"
    live = "live"


# ====================
# Request Models
# ====================

class PlaceOrderRequest(BaseModel):
    """Request model for placing an order."""
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)", example="BTC/USDT")
    side: OrderSideEnum = Field(..., description="Order side (buy or sell)")
    order_type: OrderTypeEnum = Field(OrderTypeEnum.market, description="Order type")
    quantity: float = Field(..., gt=0, description="Order quantity", example=0.1)
    price: Optional[float] = Field(None, gt=0, description="Limit price (required for limit orders)")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTC/USDT",
                "side": "buy",
                "order_type": "market",
                "quantity": 0.1
            }
        }


class StrategyParametersRequest(BaseModel):
    """Request model for updating strategy parameters."""
    base_spread: Optional[float] = Field(None, ge=0, le=0.01, description="Base spread (0-1%)")
    order_size: Optional[float] = Field(None, gt=0, description="Order size")
    max_position: Optional[float] = Field(None, gt=0, description="Maximum position size")
    signal_cooldown: Optional[int] = Field(None, ge=0, description="Signal cooldown in seconds")


class RiskLimitsRequest(BaseModel):
    """Request model for updating risk limits."""
    max_position_size: Optional[float] = Field(None, gt=0, description="Maximum position size per symbol")
    max_daily_loss_pct: Optional[float] = Field(None, ge=0, le=1, description="Maximum daily loss percentage (0-1)")
    max_drawdown_pct: Optional[float] = Field(None, ge=0, le=1, description="Maximum drawdown percentage (0-1)")


# ====================
# Response Models
# ====================

class StatusResponse(BaseModel):
    """System status response."""
    status: str = Field(..., description="System status")
    timestamp: str = Field(..., description="Current timestamp")
    trading: bool = Field(..., description="Whether trading is active")
    exchange_connected: bool = Field(..., description="Whether exchange is connected")
    mode: str = Field(..., description="Trading mode (simulated/sandbox/live)")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2026-01-09T12:00:00Z",
                "trading": True,
                "exchange_connected": True,
                "mode": "simulated"
            }
        }


class BalanceResponse(BaseModel):
    """Account balance response."""
    balances: Dict[str, float] = Field(..., description="Asset balances")

    class Config:
        json_schema_extra = {
            "example": {
                "balances": {
                    "USDT": 10000.0,
                    "BTC": 0.5,
                    "ETH": 2.0
                }
            }
        }


class TickerResponse(BaseModel):
    """Ticker data response."""
    symbol: str = Field(..., description="Trading pair")
    bid: float = Field(..., description="Best bid price")
    ask: float = Field(..., description="Best ask price")
    last: float = Field(..., description="Last trade price")
    spread: float = Field(..., description="Current spread")
    timestamp: str = Field(..., description="Ticker timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTC/USDT",
                "bid": 92999.50,
                "ask": 93000.50,
                "last": 93000.00,
                "spread": 1.00,
                "timestamp": "2026-01-09T12:00:00Z"
            }
        }


class PositionResponse(BaseModel):
    """Open position response."""
    symbol: str = Field(..., description="Trading pair")
    side: str = Field(..., description="Position side (long/short)")
    size: float = Field(..., description="Position size")
    entry_price: float = Field(..., description="Average entry price")
    current_price: Optional[float] = Field(None, description="Current market price")
    unrealized_pnl: float = Field(..., description="Unrealized P&L")
    unrealized_pnl_pct: float = Field(..., description="Unrealized P&L percentage")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTC/USDT",
                "side": "long",
                "size": 0.1,
                "entry_price": 92000.0,
                "current_price": 93000.0,
                "unrealized_pnl": 100.0,
                "unrealized_pnl_pct": 1.09
            }
        }


class RiskStatsResponse(BaseModel):
    """Risk statistics response."""
    base_capital: float = Field(..., description="Base capital")
    current_capital: float = Field(..., description="Current capital")
    total_pnl: float = Field(..., description="Total P&L")
    total_pnl_pct: float = Field(..., description="Total P&L percentage")
    daily_pnl: float = Field(..., description="Daily P&L")
    current_drawdown: float = Field(..., description="Current drawdown")
    total_trades: int = Field(..., description="Total trades executed")
    win_rate: float = Field(..., description="Win rate percentage")
    is_halted: bool = Field(..., description="Whether trading is halted")
    risk_level: str = Field(..., description="Current risk level")

    class Config:
        json_schema_extra = {
            "example": {
                "base_capital": 10000.0,
                "current_capital": 10500.0,
                "total_pnl": 500.0,
                "total_pnl_pct": 5.0,
                "daily_pnl": 150.0,
                "current_drawdown": 0.0,
                "total_trades": 42,
                "win_rate": 65.0,
                "is_halted": False,
                "risk_level": "normal"
            }
        }


class StrategyStatsResponse(BaseModel):
    """Strategy statistics response."""
    name: str = Field(..., description="Strategy name")
    is_active: bool = Field(..., description="Whether strategy is active")
    total_signals: int = Field(..., description="Total signals generated")
    winning_signals: int = Field(..., description="Winning signals")
    losing_signals: int = Field(..., description="Losing signals")
    win_rate: float = Field(..., description="Win rate percentage")
    total_pnl: float = Field(..., description="Total P&L from this strategy")


class OrderResponse(BaseModel):
    """Order execution response."""
    success: bool = Field(..., description="Whether order was successful")
    order_id: Optional[str] = Field(None, description="Order ID")
    message: str = Field(..., description="Status message")
    filled_quantity: Optional[float] = Field(None, description="Filled quantity")
    filled_price: Optional[float] = Field(None, description="Filled price")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "order_id": "ORD-12345",
                "message": "Order executed successfully",
                "filled_quantity": 0.1,
                "filled_price": 93000.0
            }
        }


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str = Field(..., description="Response message")


class SystemStatsResponse(BaseModel):
    """Complete system statistics response."""
    risk: RiskStatsResponse = Field(..., description="Risk statistics")
    strategies: List[StrategyStatsResponse] = Field(..., description="Strategy statistics")
    trading: bool = Field(..., description="Trading active status")
    ws_clients: int = Field(..., description="Connected WebSocket clients")


# ====================
# API Tags
# ====================

tags_metadata = [
    {
        "name": "System",
        "description": "System health, status, and configuration endpoints.",
    },
    {
        "name": "Trading",
        "description": "Trading control endpoints - start, stop, halt trading.",
    },
    {
        "name": "Orders",
        "description": "Order placement and management endpoints.",
    },
    {
        "name": "Positions",
        "description": "Position viewing and management endpoints.",
    },
    {
        "name": "Market Data",
        "description": "Market data endpoints - tickers, order books.",
    },
    {
        "name": "Risk",
        "description": "Risk management and statistics endpoints.",
    },
    {
        "name": "Strategies",
        "description": "Strategy management and configuration endpoints.",
    },
]


# ====================
# Router Creation
# ====================

def create_api_router() -> APIRouter:
    """Create API router with all routes documented."""
    router = APIRouter()

    # System endpoints are defined in server.py
    # This file provides the models and documentation

    return router


# Export for OpenAPI customization
openapi_info = {
    "title": "HFT Trading System API",
    "description": """
## High-Frequency Trading System API

This API provides endpoints for:

### Trading Operations
- Start/Stop/Halt trading
- Place and cancel orders
- View and manage positions

### Market Data
- Real-time ticker data
- Order book snapshots

### Risk Management
- Position limits
- Daily loss limits
- Kill switch functionality

### Strategy Management
- Activate/deactivate strategies
- Configure strategy parameters
- View strategy performance

## WebSocket

Connect to `/ws` for real-time updates:
- Ticker updates
- Position changes
- Order fills
- Strategy signals

## Authentication

Currently using API key authentication (in development).
Set `X-API-Key` header for protected endpoints.

## Rate Limits

- REST API: 100 requests/minute
- WebSocket: 10 messages/second
    """,
    "version": "1.0.0",
    "contact": {
        "name": "HFT System Support",
        "email": "support@hft-system.local",
    },
    "license_info": {
        "name": "MIT",
    },
}
