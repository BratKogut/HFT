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
- Full OpenAPI/Swagger documentation
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from exchange.exchange_adapter import create_exchange_adapter, SimulatedExchangeAdapter, CCXTExchangeAdapter
from risk.risk_manager import ProductionRiskManager, RiskLimits
from strategies.market_making_strategy import ProductionMarketMakingStrategy
from strategies.momentum_strategy import ProductionMomentumStrategy
from live.live_trading_controller import LiveTradingController, TradingConfig, TradingMode
from api.routes import (
    PlaceOrderRequest,
    StrategyParametersRequest,
    RiskLimitsRequest,
    StatusResponse,
    BalanceResponse,
    TickerResponse,
    PositionResponse,
    RiskStatsResponse,
    StrategyStatsResponse,
    OrderResponse,
    MessageResponse,
    SystemStatsResponse,
    tags_metadata,
    openapi_info,
)
from visualization.perspective_manager import PerspectiveManager, PERSPECTIVE_AVAILABLE

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
        self.live_controller: Optional[LiveTradingController] = None
        self.strategies: List = []
        self.ws_clients: List[WebSocket] = []
        self.is_trading: bool = False
        self._lock = asyncio.Lock()
        self._ws_lock = asyncio.Lock()
        # Perspective real-time visualization
        self.perspective_manager: Optional[PerspectiveManager] = None

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

        momentum_strategy = ProductionMomentumStrategy({
            'signal_cooldown': 60,
            'momentum_threshold': Decimal('0.02'),
            'rsi_period': 14,
        })
        state.strategies.append(momentum_strategy)

        logger.info(f"Strategies initialized: {[s.name for s in state.strategies]}")

        # Initialize live trading controller
        trading_config = TradingConfig(
            symbol=settings.trading_pair,
            default_order_size=Decimal("0.001"),
            max_order_size=Decimal("0.1"),
        )
        state.live_controller = LiveTradingController(
            exchange=state.exchange,
            risk_manager=state.risk_manager,
            strategies=state.strategies,
            config=trading_config,
        )
        logger.info("Live trading controller initialized")

        # Initialize Perspective visualization
        if PERSPECTIVE_AVAILABLE:
            state.perspective_manager = PerspectiveManager()
            if await state.perspective_manager.initialize():
                logger.info("Perspective visualization initialized")
                # Start background streaming task
                asyncio.create_task(stream_data_to_perspective())
                logger.info("Perspective streaming started")
            else:
                logger.warning("Perspective initialization failed")
        else:
            logger.info("Perspective not available - visualization disabled")

        logger.info("Production HFT System started successfully")
        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    finally:
        logger.info("Shutting down Production HFT System...")

        # Stop live trading if active
        if state.live_controller and state.live_controller.state.is_active:
            await state.live_controller.stop(emergency=False)

        if state.exchange:
            await state.exchange.disconnect()

        logger.info("Shutdown complete")


# Create FastAPI app with full OpenAPI documentation
app = FastAPI(
    title=openapi_info["title"],
    description=openapi_info["description"],
    version=openapi_info["version"],
    contact=openapi_info["contact"],
    license_info=openapi_info["license_info"],
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
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

# Mount static files for dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


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

@app.get(
    "/",
    tags=["System"],
    summary="Root endpoint",
    description="Returns basic system information and status.",
)
async def root():
    """Root endpoint with system information."""
    return {
        "name": "Production HFT System",
        "version": "1.0.0",
        "status": "running",
        "mode": "simulated" if settings.simulated_mode else "live",
    }


@app.get(
    "/health",
    response_model=StatusResponse,
    tags=["System"],
    summary="Health check",
    description="Check system health and connectivity status.",
)
async def health():
    """Health check endpoint with detailed status."""
    return StatusResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        trading=state.is_trading,
        exchange_connected=state.exchange is not None,
        mode="simulated" if settings.simulated_mode else ("sandbox" if settings.sandbox_mode else "live"),
    )


@app.get(
    "/stats",
    tags=["System"],
    summary="System statistics",
    description="Get comprehensive system statistics including risk and strategy metrics.",
)
async def get_stats():
    """Get complete system statistics."""
    risk_stats = state.risk_manager.get_stats() if state.risk_manager else {}
    strategy_stats = [s.get_stats() for s in state.strategies]

    return {
        "risk": risk_stats,
        "strategies": strategy_stats,
        "trading": state.is_trading,
        "ws_clients": len(state.ws_clients),
    }


@app.get(
    "/positions",
    response_model=List[PositionResponse],
    tags=["Positions"],
    summary="Get open positions",
    description="Retrieve all currently open trading positions.",
)
async def get_positions():
    """Get all open positions with P&L data."""
    if not state.risk_manager:
        return []
    return state.risk_manager.get_positions()


@app.get(
    "/balance",
    response_model=BalanceResponse,
    tags=["System"],
    summary="Get account balances",
    description="Retrieve current account balances for all assets.",
)
async def get_balance():
    """Get account balances for all assets."""
    if not state.exchange:
        raise HTTPException(status_code=503, detail="Exchange not connected")

    if isinstance(state.exchange, SimulatedExchangeAdapter):
        return BalanceResponse(balances={k: float(v) for k, v in state.exchange.balances.items()})

    # For real exchanges
    usdt = await state.exchange.get_balance("USDT")
    btc = await state.exchange.get_balance("BTC")
    return BalanceResponse(balances={"USDT": float(usdt), "BTC": float(btc)})


@app.get(
    "/ticker/{symbol}",
    response_model=TickerResponse,
    tags=["Market Data"],
    summary="Get ticker data",
    description="Get current ticker data for a trading pair including bid, ask, and last prices.",
)
async def get_ticker(symbol: str):
    """Get real-time ticker data for a symbol."""
    if not state.exchange:
        raise HTTPException(status_code=503, detail="Exchange not connected")

    ticker = await state.exchange.get_ticker(symbol)
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker not found for {symbol}")

    return TickerResponse(
        symbol=ticker.symbol,
        bid=float(ticker.bid),
        ask=float(ticker.ask),
        last=float(ticker.last),
        spread=float(ticker.ask - ticker.bid),
        timestamp=ticker.timestamp.isoformat() + "Z",
    )


@app.post(
    "/trading/start",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Start trading",
    description="Activate all strategies and begin automated trading.",
)
async def start_trading():
    """Start automated trading with all active strategies."""
    if state.is_trading:
        return MessageResponse(message="Trading already started")

    state.is_trading = True
    for strategy in state.strategies:
        strategy.activate()

    logger.info("Trading started")
    return MessageResponse(message=f"Trading started with {len(state.strategies)} strategies")


@app.post(
    "/trading/stop",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Stop trading",
    description="Gracefully stop all trading activity.",
)
async def stop_trading():
    """Stop trading gracefully, allowing open orders to complete."""
    if not state.is_trading:
        return MessageResponse(message="Trading not started")

    state.is_trading = False
    for strategy in state.strategies:
        strategy.deactivate()

    logger.info("Trading stopped")
    return MessageResponse(message="Trading stopped")


@app.post(
    "/trading/halt",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Emergency halt",
    description="Emergency halt all trading immediately. Use in case of critical issues.",
)
async def halt_trading():
    """Emergency halt - immediately stops all trading activity."""
    if state.risk_manager:
        await state.risk_manager.halt_trading("Manual halt via API")

    state.is_trading = False
    for strategy in state.strategies:
        strategy.deactivate()

    logger.warning("Trading HALTED via API")
    return MessageResponse(message="Trading halted - emergency stop activated")


@app.post(
    "/trading/resume",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Resume trading",
    description="Resume trading after an emergency halt.",
)
async def resume_trading():
    """Resume trading after emergency halt."""
    if state.risk_manager:
        await state.risk_manager.resume_trading()

    logger.info("Trading resumed via API")
    return MessageResponse(message="Trading resumed")


@app.post(
    "/strategies/{name}/activate",
    response_model=MessageResponse,
    tags=["Strategies"],
    summary="Activate strategy",
    description="Activate a specific trading strategy by name.",
)
async def activate_strategy(name: str):
    """Activate a trading strategy by its name."""
    for strategy in state.strategies:
        if strategy.name.lower() == name.lower():
            strategy.activate()
            return MessageResponse(message=f"Strategy '{name}' activated")

    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@app.post(
    "/strategies/{name}/deactivate",
    response_model=MessageResponse,
    tags=["Strategies"],
    summary="Deactivate strategy",
    description="Deactivate a specific trading strategy by name.",
)
async def deactivate_strategy(name: str):
    """Deactivate a trading strategy by its name."""
    for strategy in state.strategies:
        if strategy.name.lower() == name.lower():
            strategy.deactivate()
            return MessageResponse(message=f"Strategy '{name}' deactivated")

    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@app.get(
    "/strategies",
    tags=["Strategies"],
    summary="List strategies",
    description="Get list of all available trading strategies and their status.",
)
async def list_strategies():
    """List all available strategies with their current status."""
    return [
        {
            "name": s.name,
            "is_active": s.is_active,
            "stats": s.get_stats()
        }
        for s in state.strategies
    ]


@app.get(
    "/risk/stats",
    tags=["Risk"],
    summary="Get risk statistics",
    description="Get current risk management statistics including P&L and drawdown.",
)
async def get_risk_stats():
    """Get detailed risk management statistics."""
    if not state.risk_manager:
        raise HTTPException(status_code=503, detail="Risk manager not initialized")
    return state.risk_manager.get_stats()


@app.post(
    "/risk/halt",
    response_model=MessageResponse,
    tags=["Risk"],
    summary="Risk halt",
    description="Trigger risk-based trading halt.",
)
async def risk_halt(reason: str = Query(..., description="Reason for halt")):
    """Halt trading due to risk concerns."""
    if state.risk_manager:
        await state.risk_manager.halt_trading(reason)
    return MessageResponse(message=f"Risk halt activated: {reason}")


# ====================
# Live Trading Endpoints
# ====================

@app.get(
    "/live/status",
    tags=["Trading"],
    summary="Get live trading status",
    description="Get current live trading controller status and statistics.",
)
async def get_live_status():
    """Get live trading controller status."""
    if not state.live_controller:
        raise HTTPException(status_code=503, detail="Live controller not initialized")
    return state.live_controller.get_status()


@app.post(
    "/live/start",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Start live trading",
    description="Start automated live trading. Mode can be 'paper', 'sandbox', or 'live'.",
)
async def start_live_trading(
    mode: str = Query("paper", description="Trading mode: paper, sandbox, or live")
):
    """Start live trading with specified mode."""
    if not state.live_controller:
        raise HTTPException(status_code=503, detail="Live controller not initialized")

    mode_map = {
        "paper": TradingMode.PAPER,
        "sandbox": TradingMode.SANDBOX,
        "live": TradingMode.LIVE,
    }

    if mode.lower() not in mode_map:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    trading_mode = mode_map[mode.lower()]
    success = await state.live_controller.start(trading_mode)

    if success:
        return MessageResponse(message=f"Live trading started in {mode} mode")
    else:
        raise HTTPException(status_code=400, detail="Failed to start live trading")


@app.post(
    "/live/stop",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Stop live trading",
    description="Stop automated live trading gracefully.",
)
async def stop_live_trading(
    emergency: bool = Query(False, description="Emergency stop - close all positions")
):
    """Stop live trading."""
    if not state.live_controller:
        raise HTTPException(status_code=503, detail="Live controller not initialized")

    await state.live_controller.stop(emergency=emergency)
    return MessageResponse(
        message=f"Live trading stopped {'(emergency)' if emergency else '(graceful)'}"
    )


@app.post(
    "/live/configure",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Configure live trading",
    description="Update live trading configuration parameters.",
)
async def configure_live_trading(
    symbol: Optional[str] = Query(None, description="Trading symbol"),
    order_size: Optional[float] = Query(None, gt=0, description="Default order size"),
    max_order_size: Optional[float] = Query(None, gt=0, description="Maximum order size"),
    max_daily_trades: Optional[int] = Query(None, gt=0, description="Maximum daily trades"),
):
    """Update live trading configuration."""
    if not state.live_controller:
        raise HTTPException(status_code=503, detail="Live controller not initialized")

    if state.live_controller.state.is_active:
        raise HTTPException(status_code=400, detail="Cannot configure while trading is active")

    config = state.live_controller.config

    if symbol:
        config.symbol = symbol
    if order_size:
        config.default_order_size = Decimal(str(order_size))
    if max_order_size:
        config.max_order_size = Decimal(str(max_order_size))
    if max_daily_trades:
        config.max_daily_trades = max_daily_trades

    return MessageResponse(message="Live trading configuration updated")


@app.post(
    "/live/switch-exchange",
    response_model=MessageResponse,
    tags=["Trading"],
    summary="Switch exchange",
    description="Switch to a different exchange for live trading.",
)
async def switch_exchange(
    exchange_id: str = Query(..., description="Exchange ID (e.g., binance, kraken)"),
    sandbox: bool = Query(True, description="Use sandbox/testnet mode"),
    api_key: Optional[str] = Query(None, description="API key (optional for public endpoints)"),
    api_secret: Optional[str] = Query(None, description="API secret"),
):
    """Switch to a different exchange."""
    if state.live_controller and state.live_controller.state.is_active:
        raise HTTPException(status_code=400, detail="Stop trading before switching exchange")

    try:
        # Disconnect current exchange
        if state.exchange:
            await state.exchange.disconnect()

        # Create new exchange adapter
        new_exchange = create_exchange_adapter(
            exchange_id=exchange_id,
            api_key=api_key,
            api_secret=api_secret,
            sandbox=sandbox,
            simulated=False,
        )

        # Connect and validate
        if not await new_exchange.connect():
            raise HTTPException(status_code=503, detail=f"Failed to connect to {exchange_id}")

        state.exchange = new_exchange

        # Update live controller
        if state.live_controller:
            state.live_controller.exchange = new_exchange

        return MessageResponse(
            message=f"Switched to {exchange_id.upper()} (sandbox={sandbox})"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Visualization Endpoints
# ====================

@app.get(
    "/dashboard",
    tags=["Visualization"],
    summary="Trading Dashboard",
    description="Interactive real-time trading dashboard with Perspective viewers.",
)
async def get_dashboard():
    """Serve the Perspective dashboard."""
    dashboard_path = os.path.join(static_dir, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    raise HTTPException(status_code=404, detail="Dashboard not found")


@app.get(
    "/perspective/tables",
    tags=["Visualization"],
    summary="List Perspective tables",
    description="Get list of available Perspective tables for visualization.",
)
async def get_perspective_tables():
    """List available Perspective tables."""
    if not state.perspective_manager or not state.perspective_manager.enabled:
        raise HTTPException(status_code=503, detail="Perspective not available")
    return {"tables": state.perspective_manager.get_table_names()}


@app.websocket("/ws/perspective")
async def perspective_websocket(websocket: WebSocket):
    """WebSocket endpoint for Perspective real-time updates."""
    if not state.perspective_manager or not state.perspective_manager.enabled:
        await websocket.close(code=1003, reason="Perspective not available")
        return

    handler = state.perspective_manager.get_starlette_handler()
    if handler:
        await handler(websocket)
    else:
        await websocket.close(code=1003, reason="Perspective handler not available")


@app.post(
    "/perspective/update-trades",
    tags=["Visualization"],
    summary="Update trades table",
    description="Push trade data to Perspective visualization.",
)
async def update_perspective_trades(trades: List[Dict]):
    """Push trade data to Perspective trades table."""
    if not state.perspective_manager or not state.perspective_manager.enabled:
        raise HTTPException(status_code=503, detail="Perspective not available")
    state.perspective_manager.update_trades(trades)
    return {"status": "updated", "count": len(trades)}


@app.post(
    "/perspective/update-positions",
    tags=["Visualization"],
    summary="Update positions table",
    description="Push position data to Perspective visualization.",
)
async def update_perspective_positions(positions: List[Dict]):
    """Push position data to Perspective positions table."""
    if not state.perspective_manager or not state.perspective_manager.enabled:
        raise HTTPException(status_code=503, detail="Perspective not available")
    state.perspective_manager.update_positions(positions)
    return {"status": "updated", "count": len(positions)}


@app.post(
    "/perspective/update-signals",
    tags=["Visualization"],
    summary="Update signals table",
    description="Push signal data to Perspective visualization.",
)
async def update_perspective_signals(signals: List[Dict]):
    """Push signal data to Perspective signals table."""
    if not state.perspective_manager or not state.perspective_manager.enabled:
        raise HTTPException(status_code=503, detail="Perspective not available")
    state.perspective_manager.update_signals(signals)
    return {"status": "updated", "count": len(signals)}


@app.post(
    "/perspective/update-risk",
    tags=["Visualization"],
    summary="Update risk metrics",
    description="Push risk metrics to Perspective visualization.",
)
async def update_perspective_risk(metrics: Dict):
    """Push risk metrics to Perspective risk table."""
    if not state.perspective_manager or not state.perspective_manager.enabled:
        raise HTTPException(status_code=503, detail="Perspective not available")
    state.perspective_manager.update_risk_metrics(metrics)
    return {"status": "updated"}


async def stream_data_to_perspective():
    """Background task to stream data to Perspective tables."""
    while True:
        try:
            if state.perspective_manager and state.perspective_manager.enabled:
                # Update risk metrics from risk manager
                if state.risk_manager:
                    risk_stats = state.risk_manager.get_stats()
                    state.perspective_manager.update_risk_metrics(risk_stats)

                # Update market data from exchange
                if state.exchange and state.is_trading:
                    try:
                        ticker = await state.exchange.get_ticker(settings.trading_pair)
                        if ticker:
                            state.perspective_manager.update_market_data({
                                "symbol": ticker.symbol,
                                "last": float(ticker.last),
                                "bid": float(ticker.bid),
                                "ask": float(ticker.ask),
                                "timestamp": ticker.timestamp.isoformat(),
                            })
                    except Exception as e:
                        logger.debug(f"Failed to update market data: {e}")

            await asyncio.sleep(1)  # Update every second
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in Perspective streaming: {e}")
            await asyncio.sleep(5)


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
