# HFT MVP Tier 1 - Quick Start Guide

Get up and running in **5 minutes**! 🚀

---

## Step 1: Install Dependencies (1 minute)

```bash
cd mvp_tier1/backend
pip install -r requirements.txt
```

---

## Step 2: Configure (2 minutes)

### Copy environment template:
```bash
cp .env.example .env
```

### Edit `.env` file:

**For Binance:**
```env
EXCHANGE_NAME=binance
EXCHANGE_API_KEY=your_binance_api_key
EXCHANGE_API_SECRET=your_binance_api_secret
TRADING_MODE=paper
TRADING_PAIR=BTC/USDT
BASE_CAPITAL=10000.0
```

**For other exchanges:**
- Replace `binance` with your exchange (e.g., `kraken`, `coinbase`, `okx`)
- Get API keys from your exchange
- Make sure API keys have **read** and **trade** permissions

---

## Step 3: Run (1 minute)

```bash
python server.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 4: Access Dashboard (1 minute)

Open your browser:
```
http://localhost:8000/dashboard
```

You should see:
- System status
- Risk management stats
- Strategies (inactive by default)
- Empty positions and orders

---

## Step 5: Start Trading! (30 seconds)

### Activate a strategy:

Click one of these buttons on the dashboard:
- **"Activate Momentum"** - For momentum-based trading
- **"Activate Mean Reversion"** - For mean reversion trading

Or use the API:
```bash
curl -X POST http://localhost:8000/strategies/momentum/activate
```

### Watch it work:

- Dashboard updates every 2 seconds
- Watch for signals in the console
- See simulated orders (paper mode)
- Track PnL in real-time

---

## 🎉 You're Done!

The system is now running in **paper trading mode** (no real money at risk).

---

## Next Steps

### 1. Test Strategies (1-2 days)
- Run in paper mode for 24-48 hours
- Monitor performance
- Adjust parameters if needed

### 2. Shadow Trading (1-2 days)
- Change `TRADING_MODE=shadow` in `.env`
- Restart server
- Validate with real market data

### 3. Go Live (When ready)
⚠️ **Only after extensive testing!**
- Change `TRADING_MODE=live` in `.env`
- Start with **small capital** ($100-500)
- Monitor closely

---

## Common Issues

### Issue: "ModuleNotFoundError"
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

### Issue: "Exchange not found"
**Solution:** Check exchange name in `.env`
- Must be lowercase (e.g., `binance`, not `Binance`)
- Must be supported by CCXT

### Issue: "Authentication failed"
**Solution:** Check API keys
- Verify API key and secret are correct
- Ensure API keys have required permissions
- Check if IP whitelist is configured on exchange

### Issue: "Connection failed"
**Solution:** Check network
- Ensure internet connection is working
- Check if exchange is accessible
- Verify firewall settings

---

## API Quick Reference

```bash
# Health check
curl http://localhost:8000/health

# Get stats
curl http://localhost:8000/stats

# Get positions
curl http://localhost:8000/positions

# Get orders
curl http://localhost:8000/orders

# Activate strategy
curl -X POST http://localhost:8000/strategies/momentum/activate

# Deactivate strategy
curl -X POST http://localhost:8000/strategies/momentum/deactivate

# Halt trading
curl -X POST http://localhost:8000/trading/halt

# Resume trading
curl -X POST http://localhost:8000/trading/resume
```

---

## Tips for Success

1. **Start small:** Use paper mode first
2. **Be patient:** Let strategies run for at least 24 hours
3. **Monitor closely:** Check dashboard regularly
4. **Adjust parameters:** Fine-tune based on performance
5. **Manage risk:** Never risk more than you can afford to lose

---

## Need Help?

- Read the full README.md
- Check the API documentation
- Open an issue on GitHub

---

**Happy Trading! 🚀📈**
