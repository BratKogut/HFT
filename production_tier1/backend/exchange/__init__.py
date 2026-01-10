"""
Exchange Module
===============

Provides unified exchange connectivity for HFT system.
"""

from .exchange_adapter import (
    ExchangeAdapter,
    CCXTExchangeAdapter,
    SimulatedExchangeAdapter,
    create_exchange_adapter,
    ConnectionState,
    OrderType,
    OrderSide,
    OrderRequest,
    OrderResult,
    Ticker,
    OrderBook,
    OrderBookLevel,
    SUPPORTED_EXCHANGES,
)

__all__ = [
    "ExchangeAdapter",
    "CCXTExchangeAdapter",
    "SimulatedExchangeAdapter",
    "create_exchange_adapter",
    "ConnectionState",
    "OrderType",
    "OrderSide",
    "OrderRequest",
    "OrderResult",
    "Ticker",
    "OrderBook",
    "OrderBookLevel",
    "SUPPORTED_EXCHANGES",
]
