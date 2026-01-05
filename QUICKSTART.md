# ⚡ HFT System Tier 1 MVP - Quick Start

## 🎯 System Overview

**High-Frequency Trading System - Tier 1 MVP**

- **Type:** Medium-Frequency Trading (11-40ms latency)
- **Architecture:** Python-only (FastAPI + React)
- **Purpose:** Educational demonstrator
- **Status:** ✅ Running

---

## 🚀 Quick Start

### 1. Check System Status

```bash
sudo supervisorctl status
```

You should see:
- `hft_backend: RUNNING`
- `hft_frontend: RUNNING`
- `mongodb: RUNNING`

### 2. Access Dashboard

Open browser: **http://localhost:3000**

### 3. Start Trading

Click **🚀 Start Trading** button on the dashboard

Or via API:
```bash
curl -X POST http://localhost:8001/api/trading/start
```

### 4. Stop Trading

Click **⏹️ Stop Trading** button

Or via API:
```bash
curl -X POST http://localhost:8001/api/trading/stop
```

---

## 📊 Dashboard Features

### Main Panels:

1. **Order Book** - Real-time bid/ask display with imbalance indicator
2. **Latency Monitor** - Per-stage latency metrics and breakdown
3. **Trading Statistics** - PnL, positions, exposure
4. **Strategy Controls** - Start/Stop trading

### Real-time Updates:
- Order book updates every 500ms
- Latency metrics every 1s
- WebSocket connection status indicator

---

## 🔧 API Endpoints

### Status
```bash
GET  /api/status          # System status
GET  /api/orderbook       # Current order book
GET  /api/positions       # All positions
GET  /api/trades          # Recent trades
GET  /api/orders          # Recent orders
GET  /api/latency         # Latency statistics
```

### Trading Control
```bash
POST /api/trading/start   # Start trading
POST /api/trading/stop    # Stop trading
```

### WebSocket
```
WS   /ws                  # Real-time updates
```

---

## ⏱️ Performance

### Current Latency (Tier 1 MVP):
- Market Data: ~3ms
- Strategy: ~5ms
- Risk Checks: ~0.5ms
- Execution: ~20ms
- **Total: ~28ms** ✅

### Tier 1 Characteristics:
- ✅ Medium-frequency trading
- ✅ Suitable for market making
- ✅ Educational demonstrator
- ❌ Not Ultra-HFT (<1µs)

---

## 🎯 Strategy

### Market Making (Active)

**How it works:**
1. Monitors order book spread
2. Calculates order book imbalance
3. Generates buy/sell signals
4. Places orders to earn spread
5. Risk checks before execution

**Safety Features:**
- ✅ Canary Mode (10% size) - ENABLED
- ✅ Kill Switch
- ✅ Daily Loss Limit
- ✅ Position Limits
- ✅ Price Collars

---

## 🛠️ Configuration

### Backend (.env)
```bash
/app/backend/.env
```

Key parameters:
- `EXCHANGE_MODE=simulator` (simulator | live)
- `MAX_POSITION_SIZE=10.0`
- `MAX_ORDER_SIZE=1.0`
- `DAILY_LOSS_LIMIT=1000.0`
- `MARKET_MAKING_SPREAD=0.001` (0.1%)

### Frontend (.env)
```bash
/app/frontend/.env
```

URLs:
- `REACT_APP_BACKEND_URL=http://localhost:8001`
- `REACT_APP_WS_URL=ws://localhost:8001/ws`

---

## 📚 Documentation

Detailed documentation:
- [Architecture Documentation](./docs/ARCHITECTURE_TIER1.md)
- [HFT Blueprint](./HFT_BLUEPRINT_2026.md)
- [System Analysis](./docs/HFT_SYSTEM_ANALYSIS.md)

---

## 🐛 Troubleshooting

### Backend not running?
```bash
sudo supervisorctl restart hft_backend
tail -50 /var/log/supervisor/hft_backend.err.log
```

### Frontend not running?
```bash
sudo supervisorctl restart hft_frontend
tail -50 /var/log/supervisor/hft_frontend.err.log
```

### WebSocket not connecting?
Check CORS settings in `/app/backend/hft/config.py`

---

## ⚠️ Important Notes

### This System:
- ✅ Is an educational demonstrator
- ✅ Shows HFT architecture concepts
- ✅ Uses simulated market data
- ✅ Implements real trading logic

### This System is NOT:
- ❌ Production-ready for live trading
- ❌ Suitable for Ultra-HFT (<1µs)
- ❌ Connected to real exchanges (yet)
- ❌ A financial advice tool

---

## 📈 Next Steps

### To improve performance (Tier 2):
1. Rewrite hot path in C++
2. Implement lock-free data structures
3. Use Premium VPS (closer to exchange)
4. Add ZeroMQ for Python-C++ communication

### To go production:
1. Connect to real exchange APIs
2. Implement proper risk management
3. Add regulatory compliance
4. Extensive backtesting
5. Paper trading phase

---

## 👤 Support

For questions about architecture:
- Read: `/app/docs/ARCHITECTURE_TIER1.md`
- Check logs: `/var/log/supervisor/`

---

**Created:** January 2026  
**Type:** Tier 1 MVP (Educational)  
**Status:** ✅ Running

---

⚡ **Happy Trading!** (Educational purposes only)
