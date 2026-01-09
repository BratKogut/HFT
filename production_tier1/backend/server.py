"""
Production HFT System - Main Server
===================================

FastAPI server with WebSocket support for production trading.

Features:
- REST API for trading control
- WebSocket for real-time updates
- Exchange integration
- Risk management
- Strategy execution
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from exchange.exchange_adapter import create_exchange_adapter, SimulatedExchangeAdapter
from risk.risk_manager import ProductionRiskManager, RiskLimits
from strategies.market_making_strategy import ProductionMarketMakingStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Configuration
class Settings:
    """Application settings."""
    exchange_id: str = "binance"
    exchange_api_key: Optional[str] = None
    exchange_api_secret: Optional[str] = None
    sandbox_mode: bool = True
    simulated_mode: bool = True
    trading_pair: str = "BTC/USDT"
    initial_capital: Decimal = Decimal("10000")
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()


# State management with thread safety
class SystemState:
    """Thread-safe system state."""

    def __init__(self):
        self.exchange = None
        self.risk_manager: Optional[ProductionRiskManager] = None
        self.strategies: List = []
        self.ws_clients: List[WebSocket] = []
        self.is_trading: bool = False
        self._lock = asyncio.Lock()
        self._ws_lock = asyncio.Lock()

    async def add_ws_client(self, client: WebSocket):
        async with self._ws_lock:
            self.ws_clients.append(client)

    async def remove_ws_client(self, client: WebSocket):
        async with self._ws_lock:
            if client in self.ws_clients:
                self.ws_clients.remove(client)

    async def get_ws_clients(self) -> List[WebSocket]:
        async with self._ws_lock:
            return self.ws_clients.copy()


state = SystemState()


# Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with proper startup/shutdown."""
    logger.info("Starting Production HFT System...")

    try:
        # Initialize exchange adapter
        if settings.simulated_mode:
            state.exchange = SimulatedExchangeAdapter(
                initial_balance={'USDT': settings.initial_capital, 'BTC': Decimal('0')}
            )
        else:
            state.exchange = create_exchange_adapter(
                exchange_id=settings.exchange_id,
                api_key=settings.exchange_api_key,
                api_secret=settings.exchange_api_secret,
                sandbox=settings.sandbox_mode,
            )

        await state.exchange.connect()
        logger.info(f"Exchange connected: {'Simulated' if settings.simulated_mode else settings.exchange_id}")

        # Initialize risk manager
        limits = RiskLimits(
            max_position_size=Decimal("1.0"),
            max_position_value=Decimal("10000"),
            max_daily_loss_pct=Decimal("0.05"),
            max_drawdown_pct=Decimal("0.20"),
        )
        state.risk_manager = ProductionRiskManager(
            limits=limits,
            initial_capital=settings.initial_capital,
        )
        logger.info("Risk manager initialized")

        # Initialize strategies
        mm_strategy = ProductionMarketMakingStrategy({
            'signal_cooldown': 30,
            'base_spread': Decimal('0.0003'),
        })
        state.strategies.append(mm_strategy)
        logger.info("Strategies initialized")

        logger.info("Production HFT System started successfully")
        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    finally:
        logger.info("Shutting down Production HFT System...")

        if state.exchange:
            await state.exchange.disconnect()

        logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Production HFT System",
    description="High-Frequency Trading System - Production Tier",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - production-safe configuration
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Request/Response models
class OrderRequest(BaseModel):
    symbol: str
    side: str
    size: float
    price: Optional[float] = None


class TradeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None


# Helper functions
async def broadcast_to_clients(message: Dict):
    """Broadcast message to all WebSocket clients."""
    clients = await state.get_ws_clients()
    dead_clients = []

    for client in clients:
        try:
            await asyncio.wait_for(client.send_json(message), timeout=5.0)
        except asyncio.TimeoutError:
            dead_clients.append(client)
        except Exception:
            dead_clients.append(client)

    for client in dead_clients:
        await state.remove_ws_client(client)


# REST API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Production HFT System",
        "version": "1.0.0",
        "status": "running",
        "mode": "simulated" if settings.simulated_mode else "live",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "trading": state.is_trading,
        "exchange_connected": state.exchange is not None,
    }


@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    risk_stats = state.risk_manager.get_stats() if state.risk_manager else {}
    strategy_stats = [s.get_stats() for s in state.strategies]

    return {
        "risk": risk_stats,
        "strategies": strategy_stats,
        "trading": state.is_trading,
        "ws_clients": len(state.ws_clients),
    }


@app.get("/positions")
async def get_positions():
    """Get open positions."""
    if not state.risk_manager:
        return []
    return state.risk_manager.get_positions()


@app.get("/balance")
async def get_balance():
    """Get account balances."""
    if not state.exchange:
        raise HTTPException(status_code=503, detail="Exchange not connected")

    if isinstance(state.exchange, SimulatedExchangeAdapter):
        return {"balances": {k: float(v) for k, v in state.exchange.balances.items()}}

    # For real exchanges
    usdt = await state.exchange.get_balance("USDT")
    btc = await state.exchange.get_balance("BTC")
    return {"balances": {"USDT": float(usdt), "BTC": float(btc)}}


@app.get("/ticker/{symbol}")
async def get_ticker(symbol: str):
    """Get ticker for symbol."""
    if not state.exchange:
        raise HTTPException(status_code=503, detail="Exchange not connected")

    ticker = await state.exchange.get_ticker(symbol)
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker not found for {symbol}")

    return {
        "symbol": ticker.symbol,
        "bid": float(ticker.bid),
        "ask": float(ticker.ask),
        "last": float(ticker.last),
        "timestamp": ticker.timestamp.isoformat(),
    }


@app.post("/trading/start")
async def start_trading():
    """Start trading."""
    if state.is_trading:
        return {"message": "Trading already started"}

    state.is_trading = True
    for strategy in state.strategies:
        strategy.activate()

    logger.info("Trading started")
    return {"message": "Trading started", "strategies": len(state.strategies)}


@app.post("/trading/stop")
async def stop_trading():
    """Stop trading."""
    if not state.is_trading:
        return {"message": "Trading not started"}

    state.is_trading = False
    for strategy in state.strategies:
        strategy.deactivate()

    logger.info("Trading stopped")
    return {"message": "Trading stopped"}


@app.post("/trading/halt")
async def halt_trading():
    """Emergency halt all trading."""
    if state.risk_manager:
        await state.risk_manager.halt_trading("Manual halt via API")

    state.is_trading = False
    for strategy in state.strategies:
        strategy.deactivate()

    logger.warning("Trading HALTED via API")
    return {"message": "Trading halted"}


@app.post("/trading/resume")
async def resume_trading():
    """Resume trading after halt."""
    if state.risk_manager:
        await state.risk_manager.resume_trading()

    logger.info("Trading resumed via API")
    return {"message": "Trading resumed"}


@app.post("/strategies/{name}/activate")
async def activate_strategy(name: str):
    """Activate a strategy by name."""
    for strategy in state.strategies:
        if strategy.name.lower() == name.lower():
            strategy.activate()
            return {"message": f"Strategy '{name}' activated"}

    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@app.post("/strategies/{name}/deactivate")
async def deactivate_strategy(name: str):
    """Deactivate a strategy by name."""
    for strategy in state.strategies:
        if strategy.name.lower() == name.lower():
            strategy.deactivate()
            return {"message": f"Strategy '{name}' deactivated"}

    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    await state.add_ws_client(websocket)
    logger.info(f"WebSocket client connected. Total: {len(state.ws_clients)}")

    try:
        while True:
            try:
                # Wait for client messages or timeout
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        await state.remove_ws_client(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(state.ws_clients)}")


# Run server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
