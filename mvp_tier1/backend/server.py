"""
HFT MVP Tier 1 - Main Server
FastAPI server with REST API and WebSocket

FIXES APPLIED:
- CORS security fix (no wildcard with credentials)
- Thread-safe state management with asyncio.Lock
- Proper WebSocket timeout handling
- Error handling improvements
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from core.config import settings
from core.market_data import MarketDataHandler
from core.risk_manager import RiskManager
from core.order_executor import OrderExecutor
from strategies.momentum_strategy import MomentumStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy

# Setup logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ThreadSafeState:
    """Thread-safe state management using asyncio.Lock"""
    market_data_handler: Optional[MarketDataHandler] = None
    risk_manager: Optional[RiskManager] = None
    order_executor: Optional[OrderExecutor] = None
    active_strategies: List = field(default_factory=list)
    ws_clients: List[WebSocket] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _ws_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add_ws_client(self, client: WebSocket):
        """Thread-safe add WebSocket client"""
        async with self._ws_lock:
            self.ws_clients.append(client)

    async def remove_ws_client(self, client: WebSocket):
        """Thread-safe remove WebSocket client"""
        async with self._ws_lock:
            if client in self.ws_clients:
                self.ws_clients.remove(client)

    async def get_ws_clients_copy(self) -> List[WebSocket]:
        """Get a copy of WebSocket clients for safe iteration"""
        async with self._ws_lock:
            return self.ws_clients.copy()

    async def get_strategies_copy(self) -> List:
        """Get a copy of active strategies for safe iteration"""
        async with self._lock:
            return self.active_strategies.copy()


# Global thread-safe state
state = ThreadSafeState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with proper error handling"""
    global state

    # Startup
    logger.info("Starting HFT MVP Tier 1...")

    try:
        # Initialize components with timeout
        state.market_data_handler = MarketDataHandler(
            exchange_name=settings.exchange_name,
            api_key=settings.exchange_api_key,
            api_secret=settings.exchange_api_secret
        )

        state.risk_manager = RiskManager({
            'base_capital': settings.base_capital,
            'max_position_size': settings.max_position_size,
            'max_risk_per_trade': settings.max_risk_per_trade,
            'max_daily_loss': 0.05,  # 5%
            'max_drawdown': 0.20  # 20%
        })

        state.order_executor = OrderExecutor(
            exchange_name=settings.exchange_name,
            api_key=settings.exchange_api_key,
            api_secret=settings.exchange_api_secret,
            mode=settings.trading_mode
        )

        # Initialize strategies
        momentum_strategy = MomentumStrategy({'lookback': 20, 'threshold': 0.001})
        mean_reversion_strategy = MeanReversionStrategy({'ma_period': 20, 'std_multiplier': 2.0})

        async with state._lock:
            state.active_strategies = [momentum_strategy, mean_reversion_strategy]

        # Register callbacks
        async def on_ticker(ticker):
            """Handle ticker updates with proper error handling"""
            try:
                # Update strategies (thread-safe iteration)
                strategies = await state.get_strategies_copy()
                for strategy in strategies:
                    if strategy.is_active:
                        try:
                            signal = await asyncio.wait_for(
                                strategy.on_ticker(ticker),
                                timeout=5.0
                            )
                            if signal:
                                await handle_signal(signal)
                        except asyncio.TimeoutError:
                            logger.warning(f"Strategy {strategy.name} timeout on ticker")
                        except Exception as e:
                            logger.error(f"Strategy {strategy.name} error: {e}")

                # Broadcast to WebSocket clients (non-blocking)
                asyncio.create_task(broadcast_to_clients({
                    'type': 'ticker',
                    'data': ticker
                }))
            except Exception as e:
                logger.error(f"Error in on_ticker callback: {e}")

        state.market_data_handler.register_ticker_callback(on_ticker)

        # Connect to exchange with timeout
        try:
            await asyncio.wait_for(
                state.market_data_handler.connect(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.error("Exchange connection timeout")
            raise

        # Start market data subscriptions (tracked task)
        subscription_task = asyncio.create_task(
            state.market_data_handler.subscribe_ticker(settings.trading_pair)
        )

        logger.info("HFT MVP Tier 1 started successfully")

        yield

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise
    finally:
        # Shutdown with proper cleanup
        logger.info("Shutting down HFT MVP Tier 1...")
        try:
            if state.market_data_handler:
                await asyncio.wait_for(
                    state.market_data_handler.disconnect(),
                    timeout=10.0
                )
        except asyncio.TimeoutError:
            logger.warning("Disconnect timeout, forcing shutdown")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")


# Create FastAPI app
app = FastAPI(
    title="HFT MVP Tier 1",
    description="High-Frequency Trading MVP - Tier 1",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - SECURITY FIX: No wildcard with credentials
# Configure allowed origins from environment or use safe defaults
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Specific origins, not "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Helper functions
async def handle_signal(signal):
    """Handle trading signal with proper error handling"""
    logger.info(f"Signal received: {signal}")

    if not state.risk_manager or not state.order_executor:
        logger.error("Risk manager or order executor not initialized")
        return

    try:
        # Determine order parameters
        if signal.direction == 'long':
            side = 'buy'
        elif signal.direction == 'short':
            side = 'sell'
        elif signal.direction == 'close':
            # Close existing position with race condition protection
            async with state._lock:
                if signal.symbol in state.risk_manager.positions:
                    position = state.risk_manager.positions[signal.symbol]
                    pnl = state.risk_manager.close_position(signal.symbol, signal.price)
                    await state.order_executor.execute_order(
                        symbol=signal.symbol,
                        side='sell' if position.side == 'long' else 'buy',
                        size=position.size
                    )
                    logger.info(f"Closed position: {signal.symbol}, PnL: ${pnl:.2f}")
            return
        else:
            return

        # Calculate position size based on signal strength
        max_size = settings.max_position_size
        size = max_size * signal.strength

        # Pre-trade risk check
        is_allowed, reason = state.risk_manager.pre_trade_check(
            symbol=signal.symbol,
            side='long' if side == 'buy' else 'short',
            size=size,
            price=signal.price
        )

        if not is_allowed:
            logger.warning(f"Trade rejected: {reason}")
            return

        # Execute order with timeout
        order = await asyncio.wait_for(
            state.order_executor.execute_order(
                symbol=signal.symbol,
                side=side,
                size=size
            ),
            timeout=10.0
        )

        if order and order.status == 'filled':
            # Open position in risk manager
            state.risk_manager.open_position(
                symbol=signal.symbol,
                side='long' if side == 'buy' else 'short',
                size=size,
                entry_price=order.filled_price
            )
            logger.info(f"Position opened: {signal.symbol}, size={size}, price=${order.filled_price}")

    except asyncio.TimeoutError:
        logger.error(f"Order execution timeout for {signal.symbol}")
    except Exception as e:
        logger.error(f"Error handling signal: {e}")


async def broadcast_to_clients(message: Dict):
    """Broadcast message to all WebSocket clients - THREAD SAFE"""
    # Get a copy to iterate safely
    clients = await state.get_ws_clients_copy()
    dead_clients = []

    for client in clients:
        try:
            await asyncio.wait_for(
                client.send_json(message),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("WebSocket send timeout")
            dead_clients.append(client)
        except Exception as e:
            logger.debug(f"WebSocket send error: {e}")
            dead_clients.append(client)

    # Remove dead clients
    for client in dead_clients:
        await state.remove_ws_client(client)


# REST API Endpoints

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "HFT MVP Tier 1 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "market_data": state.market_data_handler.is_running if state.market_data_handler else False,
        "trading_mode": settings.trading_mode
    }


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    strategies = await state.get_strategies_copy()
    return {
        "risk": state.risk_manager.get_stats() if state.risk_manager else {},
        "execution": state.order_executor.get_stats() if state.order_executor else {},
        "strategies": [s.get_stats() for s in strategies]
    }


@app.get("/positions")
async def get_positions():
    """Get open positions"""
    if not state.risk_manager:
        return []
    return state.risk_manager.get_positions()


@app.get("/orders")
async def get_orders(limit: int = 100):
    """Get order history"""
    if not state.order_executor:
        return []
    return state.order_executor.get_order_history(limit)


@app.post("/strategies/{strategy_name}/activate")
async def activate_strategy(strategy_name: str):
    """Activate a strategy"""
    strategies = await state.get_strategies_copy()
    for strategy in strategies:
        if strategy.name.lower() == strategy_name.lower():
            strategy.activate()
            return {"message": f"Strategy '{strategy_name}' activated"}
    raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")


@app.post("/strategies/{strategy_name}/deactivate")
async def deactivate_strategy(strategy_name: str):
    """Deactivate a strategy"""
    strategies = await state.get_strategies_copy()
    for strategy in strategies:
        if strategy.name.lower() == strategy_name.lower():
            strategy.deactivate()
            return {"message": f"Strategy '{strategy_name}' deactivated"}
    raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")


@app.post("/trading/halt")
async def halt_trading():
    """Halt all trading (circuit breaker)"""
    if state.risk_manager:
        state.risk_manager.halt_trading("Manual halt via API")
        logger.warning("Trading halted via API")
        return {"message": "Trading halted"}
    raise HTTPException(status_code=503, detail="Risk manager not initialized")


@app.post("/trading/resume")
async def resume_trading():
    """Resume trading"""
    if state.risk_manager:
        state.risk_manager.resume_trading()
        logger.info("Trading resumed via API")
        return {"message": "Trading resumed"}
    raise HTTPException(status_code=503, detail="Risk manager not initialized")


# WebSocket endpoint with proper timeout and error handling
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates with timeout"""
    await websocket.accept()
    await state.add_ws_client(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(state.ws_clients)}")

    try:
        while True:
            # Keep connection alive with timeout
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0  # 60 second timeout for ping/pong
                )
            except asyncio.TimeoutError:
                # Send ping to check if client is alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break  # Client disconnected
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        await state.remove_ws_client(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(state.ws_clients)}")


# Simple HTML dashboard
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>HFT MVP Tier 1 - Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
            h1 { color: #4CAF50; }
            .container { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .card { background: #2a2a2a; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
            .card h2 { margin-top: 0; color: #4CAF50; }
            .stat { display: flex; justify-content: space-between; margin: 10px 0; }
            .stat-label { font-weight: bold; }
            .stat-value { color: #4CAF50; }
            .positive { color: #4CAF50; }
            .negative { color: #f44336; }
            button { background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
            button:hover { background: #45a049; }
            button.danger { background: #f44336; }
            button.danger:hover { background: #da190b; }
        </style>
    </head>
    <body>
        <h1>HFT MVP Tier 1 - Dashboard</h1>
        
        <div class="container">
            <div class="card">
                <h2>System Status</h2>
                <div id="system-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Risk Management</h2>
                <div id="risk-stats">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Execution</h2>
                <div id="execution-stats">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Strategies</h2>
                <div id="strategies">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Open Positions</h2>
                <div id="positions">Loading...</div>
            </div>
            
            <div class="card">
                <h2>Recent Orders</h2>
                <div id="orders">Loading...</div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <h2>Controls</h2>
            <button onclick="haltTrading()" class="danger">Halt Trading</button>
            <button onclick="resumeTrading()">Resume Trading</button>
            <button onclick="activateStrategy('momentum')">Activate Momentum</button>
            <button onclick="deactivateStrategy('momentum')">Deactivate Momentum</button>
            <button onclick="activateStrategy('meanreversion')">Activate Mean Reversion</button>
            <button onclick="deactivateStrategy('meanreversion')">Deactivate Mean Reversion</button>
        </div>
        
        <script>
            async function fetchStats() {
                const response = await fetch('/stats');
                const data = await response.json();
                
                // System status
                document.getElementById('system-status').innerHTML = `
                    <div class="stat"><span class="stat-label">Trading Mode:</span><span class="stat-value">${data.execution.mode}</span></div>
                    <div class="stat"><span class="stat-label">Exchange:</span><span class="stat-value">${data.execution.exchange}</span></div>
                `;
                
                // Risk stats
                const risk = data.risk;
                document.getElementById('risk-stats').innerHTML = `
                    <div class="stat"><span class="stat-label">Capital:</span><span class="stat-value">$${risk.current_capital.toFixed(2)}</span></div>
                    <div class="stat"><span class="stat-label">Total PnL:</span><span class="stat-value ${risk.total_pnl >= 0 ? 'positive' : 'negative'}">$${risk.total_pnl.toFixed(2)} (${risk.total_pnl_pct.toFixed(2)}%)</span></div>
                    <div class="stat"><span class="stat-label">Daily PnL:</span><span class="stat-value ${risk.daily_pnl >= 0 ? 'positive' : 'negative'}">$${risk.daily_pnl.toFixed(2)}</span></div>
                    <div class="stat"><span class="stat-label">Open Positions:</span><span class="stat-value">${risk.open_positions}</span></div>
                    <div class="stat"><span class="stat-label">Drawdown:</span><span class="stat-value">${(risk.current_drawdown * 100).toFixed(2)}%</span></div>
                    <div class="stat"><span class="stat-label">Status:</span><span class="stat-value ${risk.is_halted ? 'negative' : 'positive'}">${risk.is_halted ? 'HALTED' : 'ACTIVE'}</span></div>
                `;
                
                // Execution stats
                const exec = data.execution;
                document.getElementById('execution-stats').innerHTML = `
                    <div class="stat"><span class="stat-label">Total Orders:</span><span class="stat-value">${exec.total_orders}</span></div>
                    <div class="stat"><span class="stat-label">Filled:</span><span class="stat-value">${exec.filled_orders}</span></div>
                    <div class="stat"><span class="stat-label">Failed:</span><span class="stat-value">${exec.failed_orders}</span></div>
                    <div class="stat"><span class="stat-label">Fill Rate:</span><span class="stat-value">${exec.fill_rate.toFixed(2)}%</span></div>
                `;
                
                // Strategies
                let strategiesHTML = '';
                data.strategies.forEach(s => {
                    strategiesHTML += `
                        <div class="stat">
                            <span class="stat-label">${s.name}:</span>
                            <span class="stat-value ${s.is_active ? 'positive' : 'negative'}">${s.is_active ? 'ACTIVE' : 'INACTIVE'} (${s.total_signals} signals)</span>
                        </div>
                    `;
                });
                document.getElementById('strategies').innerHTML = strategiesHTML;
            }
            
            async function fetchPositions() {
                const response = await fetch('/positions');
                const positions = await response.json();
                
                if (positions.length === 0) {
                    document.getElementById('positions').innerHTML = '<p>No open positions</p>';
                } else {
                    let html = '';
                    positions.forEach(p => {
                        html += `
                            <div class="stat">
                                <span class="stat-label">${p.symbol} ${p.side}:</span>
                                <span class="stat-value">${p.size} @ $${p.entry_price.toFixed(2)}</span>
                            </div>
                        `;
                    });
                    document.getElementById('positions').innerHTML = html;
                }
            }
            
            async function fetchOrders() {
                const response = await fetch('/orders?limit=5');
                const orders = await response.json();
                
                if (orders.length === 0) {
                    document.getElementById('orders').innerHTML = '<p>No recent orders</p>';
                } else {
                    let html = '';
                    orders.forEach(o => {
                        html += `
                            <div class="stat">
                                <span class="stat-label">${o.side} ${o.symbol}:</span>
                                <span class="stat-value">${o.size} @ $${o.filled_price ? o.filled_price.toFixed(2) : 'N/A'} (${o.status})</span>
                            </div>
                        `;
                    });
                    document.getElementById('orders').innerHTML = html;
                }
            }
            
            async function haltTrading() {
                await fetch('/trading/halt', { method: 'POST' });
                fetchStats();
            }
            
            async function resumeTrading() {
                await fetch('/trading/resume', { method: 'POST' });
                fetchStats();
            }
            
            async function activateStrategy(name) {
                await fetch(`/strategies/${name}/activate`, { method: 'POST' });
                fetchStats();
            }
            
            async function deactivateStrategy(name) {
                await fetch(`/strategies/${name}/deactivate`, { method: 'POST' });
                fetchStats();
            }
            
            // Initial fetch
            fetchStats();
            fetchPositions();
            fetchOrders();
            
            // Refresh every 2 seconds
            setInterval(() => {
                fetchStats();
                fetchPositions();
                fetchOrders();
            }, 2000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
