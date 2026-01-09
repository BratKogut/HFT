"""HFT System - FastAPI Server with WebSocket Support"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import os
from datetime import datetime
import json

from hft.config import settings
from hft.market_data_handler import MarketDataHandler
from hft.strategy_engine import StrategyEngine
from hft.order_executor import OrderExecutor
from hft.risk_manager import RiskManager
from hft.position_tracker import PositionTracker
from hft.latency_monitor import LatencyMonitor

# Initialize FastAPI
app = FastAPI(
    title="HFT System Tier 1 MVP",
    description="High-Frequency Trading System - Medium Frequency (11-40ms)",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class SystemState:
    def __init__(self):
        self.db_client: AsyncIOMotorClient = None
        self.db = None
        self.market_data_handler: MarketDataHandler = None
        self.strategy_engine: StrategyEngine = None
        self.order_executor: OrderExecutor = None
        self.risk_manager: RiskManager = None
        self.position_tracker: PositionTracker = None
        self.latency_monitor: LatencyMonitor = None
        self.is_trading = False
        self.websocket_clients = set()

state = SystemState()

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    print("🚀 Starting HFT System Tier 1 MVP...")
    
    # Connect to MongoDB
    state.db_client = AsyncIOMotorClient(settings.mongo_url)
    state.db = state.db_client[settings.mongo_db]
    print(f"✅ Connected to MongoDB: {settings.mongo_db}")
    
    # Initialize components
    state.latency_monitor = LatencyMonitor()
    state.risk_manager = RiskManager(settings)
    state.position_tracker = PositionTracker(state.db)
    state.order_executor = OrderExecutor(state.db, state.latency_monitor)
    state.strategy_engine = StrategyEngine(settings, state.latency_monitor)
    state.market_data_handler = MarketDataHandler(
        settings,
        state.strategy_engine,
        state.latency_monitor
    )
    
    print("✅ All components initialized")
    print(f"📊 Default Symbol: {settings.default_symbol}")
    print(f"⚙️  Exchange Mode: {settings.exchange_mode}")
    print("\n🎯 HFT System Ready!\n")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("\n🛑 Shutting down HFT System...")
    
    if state.is_trading:
        await stop_trading()
    
    if state.market_data_handler:
        await state.market_data_handler.stop()
    
    if state.db_client:
        state.db_client.close()
    
    print("✅ Shutdown complete")

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.websocket_clients.add(websocket)
    print(f"✅ WebSocket client connected (total: {len(state.websocket_clients)})")
    
    try:
        while True:
            # Send periodic updates
            data = await get_system_status()
            await websocket.send_json(data)
            await asyncio.sleep(0.1)  # 100ms updates
    except WebSocketDisconnect:
        state.websocket_clients.remove(websocket)
        print(f"❌ WebSocket client disconnected (total: {len(state.websocket_clients)})")

# Broadcast to all WebSocket clients
async def broadcast(data: dict):
    """Broadcast data to all connected WebSocket clients"""
    if state.websocket_clients:
        dead_clients = set()
        for client in state.websocket_clients:
            try:
                await client.send_json(data)
            except Exception:
                dead_clients.add(client)
        state.websocket_clients -= dead_clients

# REST API Endpoints

@app.get("/")
async def root():
    return {
        "name": "HFT System Tier 1 MVP",
        "version": "1.0.0",
        "status": "running",
        "exchange_mode": settings.exchange_mode
    }

@app.get("/api/status")
async def get_system_status():
    """Get system status"""
    latency_stats = state.latency_monitor.get_stats() if state.latency_monitor else {}
    positions = await state.position_tracker.get_all_positions() if state.position_tracker else []
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "is_trading": state.is_trading,
        "symbol": settings.default_symbol,
        "exchange_mode": settings.exchange_mode,
        "latency": latency_stats,
        "positions": positions,
        "connected_clients": len(state.websocket_clients)
    }

@app.post("/api/trading/start")
async def start_trading():
    """Start trading"""
    if state.is_trading:
        return {"status": "error", "message": "Trading already active"}
    
    try:
        # Start market data
        await state.market_data_handler.start(settings.default_symbol)
        state.is_trading = True
        
        print("✅ Trading started")
        await broadcast({"type": "trading_status", "status": "started"})
        
        return {"status": "success", "message": "Trading started"}
    except Exception as e:
        print(f"❌ Error starting trading: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/trading/stop")
async def stop_trading():
    """Stop trading"""
    if not state.is_trading:
        return {"status": "error", "message": "Trading not active"}
    
    try:
        await state.market_data_handler.stop()
        state.is_trading = False
        
        print("✅ Trading stopped")
        await broadcast({"type": "trading_status", "status": "stopped"})
        
        return {"status": "success", "message": "Trading stopped"}
    except Exception as e:
        print(f"❌ Error stopping trading: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/orderbook")
async def get_orderbook():
    """Get current order book"""
    if not state.market_data_handler:
        return {"error": "Market data not initialized"}
    
    order_book = state.market_data_handler.get_order_book()
    return order_book

@app.get("/api/positions")
async def get_positions():
    """Get all positions"""
    positions = await state.position_tracker.get_all_positions()
    return {"positions": positions}

@app.get("/api/trades")
async def get_trades(limit: int = 100):
    """Get recent trades"""
    trades = await state.db.trades.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return {"trades": trades}

@app.get("/api/orders")
async def get_orders(limit: int = 100):
    """Get recent orders"""
    orders = await state.db.orders.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return {"orders": orders}

@app.get("/api/latency")
async def get_latency_stats():
    """Get latency statistics"""
    return state.latency_monitor.get_stats()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info"
    )
