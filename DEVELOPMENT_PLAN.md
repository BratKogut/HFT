# HFT SYSTEM - KOMPLEKSOWY PLAN ROZWOJU

**Data:** 6 stycznia 2026
**Wersja:** 1.0
**Autor:** Analiza techniczna i testy

---

## EXECUTIVE SUMMARY

### Stan Obecny
- **Ocena systemu:** 2.0/5 (wymaga znaczących poprawek)
- **Problemy znalezione:** 155 (47 krytycznych, 51 wysokich)
- **Backtesty:** 32 kombinacje (8 par × 4 strategie)
- **Status:** System edukacyjny/symulator, NIE gotowy do produkcji

### Wyniki Testów
| Strategia | Avg Return | Avg Sharpe | Profitable Pairs | Rekomendacja |
|-----------|------------|------------|------------------|--------------|
| **Market Making** | +3.38% | 88.62 | 8/8 (100%) | ✅ GŁÓWNA |
| **Momentum** | +0.79% | 275.05 | 7/7 (100%) | ✅ WSPIERAJĄCA |
| Vol Breakout | +0.29% | -3.96 | 5/8 (63%) | ⚠️ WARUNKOWA |
| Mean Reversion | -3.64% | -227.02 | 0/8 (0%) | ❌ NIE UŻYWAĆ |

### Najlepsze Pary Tradingowe
1. **AVAX/USDT** - Score: 184.5 (Vol Breakout)
2. **XRP/USDT** - Score: 111.6 (Vol Breakout)
3. **MATIC/USDT** - Score: 91.2 (Momentum)
4. **SOL/USDT** - Score: 72.0 (Momentum)
5. **BTC/USDT** - Score: 68.4 (Market Making)

---

## FAZA 1: NAPRAWY KRYTYCZNE (Tydzień 1-2)

### 1.1 Bezpieczeństwo - NATYCHMIAST

| Problem | Lokalizacja | Priorytet | Effort |
|---------|-------------|-----------|--------|
| CORS Vulnerability | `mvp_tier1/server.py:115-121` | 🔴 | 1h |
| API Credentials Exposure | `ccxt_order_executor.py:67-68` | 🔴 | 2h |
| getattr() bez walidacji | `data_downloader.py:49` | 🔴 | 1h |
| Brakujące moduły | `production_tier1/models/` | 🔴 | 4h |

**Akcje:**
```python
# 1. Naprawić CORS
allow_origins=["http://localhost:3000"],  # Nie ["*"]
allow_credentials=False,  # Lub True tylko z specific origins

# 2. Walidacja exchange_name
ALLOWED_EXCHANGES = ['binance', 'bybit', 'okx', 'kraken']
if exchange_name.lower() not in ALLOWED_EXCHANGES:
    raise ValueError(f"Invalid exchange: {exchange_name}")

# 3. Szyfrowanie credentials
from cryptography.fernet import Fernet
# Store encrypted, decrypt only when needed
```

### 1.2 Race Conditions - Tydzień 1

| Problem | Lokalizacja | Rozwiązanie |
|---------|-------------|-------------|
| WebSocket broadcast | `server.py:182-188` | `asyncio.Lock()` |
| Global state | `server.py:29-34` | Lock + thread-safe dict |
| Position tracker | `position_tracker.py` | Atomic operations |
| Order executor | `order_executor.py:37-40` | Transaction pattern |

**Implementacja:**
```python
import asyncio
from collections.abc import Mapping

class ThreadSafeState:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._ws_clients = []
        self._active_strategies = []

    async def broadcast(self, message):
        async with self._lock:
            clients_copy = self._ws_clients.copy()

        for client in clients_copy:
            try:
                await client.send_json(message)
            except:
                async with self._lock:
                    if client in self._ws_clients:
                        self._ws_clients.remove(client)
```

### 1.3 Error Handling - Tydzień 2

**Dodać timeout'y:**
```python
import asyncio

async def safe_exchange_call(coro, timeout_seconds=10):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"Exchange call timed out after {timeout_seconds}s")
        raise
    except Exception as e:
        logger.error(f"Exchange call failed: {e}")
        raise
```

**Circuit Breaker:**
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure > self.reset_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpen()

        try:
            result = await func(*args, **kwargs)
            self.failures = 0
            self.state = 'CLOSED'
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.threshold:
                self.state = 'OPEN'
            raise
```

---

## FAZA 2: INTEGRACJA Z GIEŁDAMI (Tydzień 3-4)

### 2.1 Architektura Exchange Adapter

```
┌─────────────────────────────────────────────────────────┐
│                    Exchange Adapter                      │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Binance    │  │    Bybit     │  │     OKX      │  │
│  │   Adapter    │  │   Adapter    │  │   Adapter    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │          │
│  ┌──────┴─────────────────┴─────────────────┴──────┐   │
│  │            Unified Exchange Interface            │   │
│  │  - connect()     - subscribe_orderbook()        │   │
│  │  - place_order() - subscribe_trades()           │   │
│  │  - cancel_order()- get_balance()                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 CCXT Pro Integration

```python
# exchange_adapter.py
import ccxt.pro as ccxtpro
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable
import asyncio

class ExchangeAdapter(ABC):
    """Unified exchange interface"""

    @abstractmethod
    async def connect(self) -> bool:
        pass

    @abstractmethod
    async def subscribe_orderbook(self, symbol: str, callback: Callable) -> None:
        pass

    @abstractmethod
    async def place_order(self, symbol: str, side: str, order_type: str,
                         amount: float, price: Optional[float] = None) -> Dict:
        pass


class BinanceAdapter(ExchangeAdapter):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.exchange = ccxtpro.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'sandboxMode': testnet
            }
        })
        self._running = False
        self._callbacks = {}

    async def connect(self) -> bool:
        try:
            await self.exchange.load_markets()
            self._running = True
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def subscribe_orderbook(self, symbol: str, callback: Callable) -> None:
        self._callbacks[f"orderbook:{symbol}"] = callback
        asyncio.create_task(self._orderbook_loop(symbol))

    async def _orderbook_loop(self, symbol: str):
        callback = self._callbacks.get(f"orderbook:{symbol}")
        while self._running:
            try:
                orderbook = await asyncio.wait_for(
                    self.exchange.watch_order_book(symbol, limit=20),
                    timeout=30
                )
                if callback:
                    await callback(orderbook)
            except asyncio.TimeoutError:
                logger.warning(f"Orderbook timeout for {symbol}")
            except Exception as e:
                logger.error(f"Orderbook error: {e}")
                await asyncio.sleep(1)
```

### 2.3 Paper Trading Mode

```python
class PaperTradingExecutor:
    """Simulates order execution for testing"""

    def __init__(self, initial_balance: Dict[str, float]):
        self.balances = initial_balance.copy()
        self.positions = {}
        self.orders = []
        self.fills = []

    async def place_order(self, symbol: str, side: str, amount: float,
                         price: float, slippage: float = 0.001) -> Dict:
        base, quote = symbol.split('/')

        # Apply slippage
        if side == 'buy':
            fill_price = price * (1 + slippage)
            cost = amount * fill_price
            if self.balances.get(quote, 0) < cost:
                return {'success': False, 'error': 'Insufficient balance'}
            self.balances[quote] -= cost
            self.balances[base] = self.balances.get(base, 0) + amount
        else:
            fill_price = price * (1 - slippage)
            if self.balances.get(base, 0) < amount:
                return {'success': False, 'error': 'Insufficient balance'}
            self.balances[base] -= amount
            self.balances[quote] = self.balances.get(quote, 0) + amount * fill_price

        order = {
            'id': str(uuid.uuid4()),
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'price': fill_price,
            'timestamp': datetime.utcnow(),
            'status': 'filled'
        }
        self.orders.append(order)
        return {'success': True, 'order': order}
```

---

## FAZA 3: STRATEGIE PRODUKCYJNE (Tydzień 5-6)

### 3.1 Market Making Strategy (Główna)

Bazując na wynikach testów (+3.38% avg return, 100% profitable pairs):

```python
class ProductionMarketMaking:
    """
    Enhanced market making with:
    - Inventory management
    - Dynamic spread adjustment
    - Trend awareness
    - Risk controls
    """

    def __init__(self, config: MarketMakingConfig):
        self.base_spread_bps = config.base_spread_bps  # 3-5 bps
        self.max_position_usd = config.max_position_usd
        self.order_size_usd = config.order_size_usd
        self.inventory_target = 0.0  # Neutral inventory

        # Dynamic parameters
        self.spread_multiplier = 1.0
        self.last_signal_time = None
        self.cooldown_seconds = 60

        # Indicators
        self.ema_fast = EMA(period=20)
        self.ema_slow = EMA(period=60)
        self.volatility = RollingStd(period=60)

    async def on_orderbook_update(self, orderbook: Dict) -> Optional[Signal]:
        """Process orderbook update and generate signals"""

        mid_price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
        spread = orderbook['asks'][0][0] - orderbook['bids'][0][0]
        spread_bps = spread / mid_price * 10000

        # Update indicators
        self.ema_fast.update(mid_price)
        self.ema_slow.update(mid_price)
        self.volatility.update(mid_price)

        # Calculate trend
        if self.ema_fast.value and self.ema_slow.value:
            trend = (self.ema_fast.value - self.ema_slow.value) / self.ema_slow.value
        else:
            return None

        # Cooldown check
        if self.last_signal_time:
            if (datetime.utcnow() - self.last_signal_time).total_seconds() < self.cooldown_seconds:
                return None

        # Adjust spread based on volatility
        vol_pct = self.volatility.value / mid_price if self.volatility.value else 0
        self.spread_multiplier = 1.0 + vol_pct * 10  # Higher vol = wider spread

        target_spread_bps = self.base_spread_bps * self.spread_multiplier

        # Only trade if spread is favorable
        if spread_bps < target_spread_bps * 0.5:
            return None

        # Generate signal based on trend
        signal = None
        order_size = self.order_size_usd / mid_price

        if trend > 0.002:  # Uptrend - buy bias
            if self._can_buy(mid_price):
                signal = Signal(
                    side='buy',
                    price=mid_price * (1 - target_spread_bps / 20000),
                    size=order_size,
                    reason=f'mm_uptrend_{trend*100:.2f}%'
                )
        elif trend < -0.002:  # Downtrend - sell bias
            if self._can_sell(order_size):
                signal = Signal(
                    side='sell',
                    price=mid_price * (1 + target_spread_bps / 20000),
                    size=order_size,
                    reason=f'mm_downtrend_{trend*100:.2f}%'
                )
        else:  # Range - provide liquidity both sides
            if vol_pct > 0.01 and self._can_buy(mid_price):
                signal = Signal(
                    side='buy',
                    price=mid_price * (1 - target_spread_bps / 20000),
                    size=order_size * 0.5,
                    reason=f'mm_range_vol_{vol_pct*100:.2f}%'
                )

        if signal:
            self.last_signal_time = datetime.utcnow()

        return signal
```

### 3.2 Momentum Strategy (Wspierająca)

Bazując na wynikach (+0.79% return, 275 Sharpe, 89.8% win rate):

```python
class ProductionMomentum:
    """
    Momentum strategy with RSI filter
    Best for: DOGE, MATIC, SOL
    """

    def __init__(self, config: MomentumConfig):
        self.lookback = config.lookback  # 30 bars
        self.rsi_period = config.rsi_period  # 14 bars
        self.entry_threshold = config.entry_threshold  # 2%
        self.rsi_overbought = config.rsi_overbought  # 70
        self.rsi_oversold = config.rsi_oversold  # 30

        self.price_history = deque(maxlen=self.lookback + 20)
        self.position = None

    def update(self, price: float) -> Optional[Signal]:
        self.price_history.append(price)

        if len(self.price_history) < self.lookback + 10:
            return None

        prices = list(self.price_history)

        # Calculate momentum
        momentum = (prices[-1] - prices[-self.lookback]) / prices[-self.lookback]

        # Calculate RSI
        rsi = self._calculate_rsi(prices)

        # Generate signals
        if self.position is None:
            # Entry conditions
            if momentum > self.entry_threshold and rsi < self.rsi_overbought:
                return Signal(
                    side='buy',
                    price=prices[-1],
                    reason=f'momentum_entry_rsi{rsi:.0f}'
                )
        else:
            # Exit conditions
            if rsi > 75:  # Overbought exit
                return Signal(
                    side='sell',
                    price=prices[-1],
                    reason=f'overbought_exit_rsi{rsi:.0f}'
                )

            # Stop loss
            pnl_pct = (prices[-1] - self.position['entry_price']) / self.position['entry_price']
            if pnl_pct < -0.02:
                return Signal(
                    side='sell',
                    price=prices[-1],
                    reason='stop_loss'
                )

        return None
```

### 3.3 Rekomendowane Konfiguracje Par

| Para | Strategia Główna | Strategia Backup | Max Position | Spread Target |
|------|------------------|------------------|--------------|---------------|
| **BTC/USDT** | Market Making | - | $2,000 | 3 bps |
| **ETH/USDT** | Market Making | Momentum | $1,500 | 4 bps |
| **SOL/USDT** | Market Making | Momentum | $1,000 | 5 bps |
| **AVAX/USDT** | Vol Breakout | Market Making | $800 | 5 bps |
| **DOGE/USDT** | Momentum | Market Making | $500 | 8 bps |
| **XRP/USDT** | Market Making | Momentum | $800 | 5 bps |
| **MATIC/USDT** | Momentum | Market Making | $600 | 6 bps |
| **LINK/USDT** | Momentum | Market Making | $700 | 5 bps |

---

## FAZA 4: RISK MANAGEMENT (Tydzień 7-8)

### 4.1 Position Limits

```python
class RiskManager:
    def __init__(self, config: RiskConfig):
        self.max_position_per_symbol = config.max_position_per_symbol
        self.max_total_exposure = config.max_total_exposure
        self.max_daily_loss = config.max_daily_loss
        self.max_drawdown = config.max_drawdown

        self.daily_pnl = 0.0
        self.peak_equity = config.initial_capital
        self.current_equity = config.initial_capital
        self.is_halted = False

    def check_order(self, order: Order, positions: Dict) -> Tuple[bool, str]:
        """Validate order against risk limits"""

        if self.is_halted:
            return False, "Trading halted"

        # Check daily loss
        if self.daily_pnl < -self.max_daily_loss:
            self.is_halted = True
            return False, f"Daily loss limit reached: ${self.daily_pnl:.2f}"

        # Check drawdown
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        if drawdown > self.max_drawdown:
            self.is_halted = True
            return False, f"Max drawdown reached: {drawdown*100:.2f}%"

        # Check position size
        current_position = positions.get(order.symbol, 0)
        new_position = current_position + (order.size if order.side == 'buy' else -order.size)

        if abs(new_position * order.price) > self.max_position_per_symbol:
            return False, f"Position limit exceeded for {order.symbol}"

        # Check total exposure
        total_exposure = sum(abs(p * order.price) for p in positions.values())
        if total_exposure > self.max_total_exposure:
            return False, "Total exposure limit exceeded"

        return True, "OK"
```

### 4.2 Kill Switch

```python
class KillSwitch:
    """Emergency stop mechanism"""

    def __init__(self, exchange_adapter: ExchangeAdapter):
        self.exchange = exchange_adapter
        self.is_triggered = False
        self.trigger_reasons = []

    async def trigger(self, reason: str):
        """Trigger kill switch - cancel all orders, close all positions"""
        self.is_triggered = True
        self.trigger_reasons.append(f"{datetime.utcnow()}: {reason}")

        logger.critical(f"🚨 KILL SWITCH TRIGGERED: {reason}")

        # Cancel all open orders
        try:
            await self.exchange.cancel_all_orders()
            logger.info("All orders cancelled")
        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")

        # Close all positions (market orders)
        try:
            positions = await self.exchange.get_positions()
            for symbol, position in positions.items():
                if position['size'] != 0:
                    side = 'sell' if position['size'] > 0 else 'buy'
                    await self.exchange.place_order(
                        symbol=symbol,
                        side=side,
                        order_type='market',
                        amount=abs(position['size'])
                    )
            logger.info("All positions closed")
        except Exception as e:
            logger.error(f"Failed to close positions: {e}")

        # Send alerts
        await self._send_alerts(reason)

    async def _send_alerts(self, reason: str):
        """Send alerts via configured channels"""
        # Implement Telegram, Discord, Email alerts
        pass
```

---

## FAZA 5: MONITORING & DEPLOYMENT (Tydzień 9-10)

### 5.1 Metryki do Monitorowania

```python
# metrics.py
from prometheus_client import Counter, Gauge, Histogram, Summary

# Trading metrics
orders_total = Counter('hft_orders_total', 'Total orders placed', ['symbol', 'side', 'status'])
fills_total = Counter('hft_fills_total', 'Total fills received', ['symbol', 'side'])
pnl_total = Gauge('hft_pnl_total', 'Total PnL in USD')
position_value = Gauge('hft_position_value', 'Position value in USD', ['symbol'])

# Performance metrics
latency_orderbook = Histogram('hft_latency_orderbook_ms', 'Orderbook processing latency')
latency_order_placement = Histogram('hft_latency_order_ms', 'Order placement latency')
sharpe_ratio = Gauge('hft_sharpe_ratio', 'Rolling Sharpe ratio')

# System metrics
websocket_reconnects = Counter('hft_ws_reconnects', 'WebSocket reconnection count', ['exchange'])
errors_total = Counter('hft_errors_total', 'Total errors', ['type'])
```

### 5.2 Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  hft-backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - EXCHANGE_API_KEY=${EXCHANGE_API_KEY}
      - EXCHANGE_API_SECRET=${EXCHANGE_API_SECRET}
      - REDIS_URL=redis://redis:6379
      - MONGO_URL=mongodb://mongo:27017/hft
    depends_on:
      - redis
      - mongo
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  mongo:
    image: mongo:6
    volumes:
      - mongo_data:/data/db

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  redis_data:
  mongo_data:
  grafana_data:
```

---

## FAZA 6: TESTOWANIE PRODUKCYJNE (Tydzień 11-12)

### 6.1 Plan Testów

| Etap | Czas | Kapitał | Cel |
|------|------|---------|-----|
| Paper Trading | 2 tygodnie | $0 (symulacja) | Walidacja strategii |
| Testnet | 1 tydzień | Testnet funds | Test integracji |
| Shadow Trading | 1 tydzień | $0 (log only) | Porównanie z live |
| Live (Min) | 2 tygodnie | $1,000 | Initial validation |
| Live (Scale) | Ongoing | $5,000+ | Production |

### 6.2 Kryteria Sukcesu

**Paper Trading Pass:**
- [ ] Sharpe > 1.5
- [ ] Max Drawdown < 5%
- [ ] Win Rate > 50%
- [ ] Profit Factor > 1.5
- [ ] Minimum 100 trades

**Production Go-Live:**
- [ ] 2 tygodnie profitable paper trading
- [ ] Zero critical bugs
- [ ] All risk controls working
- [ ] Monitoring fully operational
- [ ] Alerting tested

---

## TIMELINE PODSUMOWANIE

```
Tydzień 1-2:   [████████████████] Naprawy Krytyczne (Bezpieczeństwo, Race Conditions)
Tydzień 3-4:   [████████████████] Integracja z Giełdami (CCXT Pro, Paper Trading)
Tydzień 5-6:   [████████████████] Strategie Produkcyjne (Market Making, Momentum)
Tydzień 7-8:   [████████████████] Risk Management (Limits, Kill Switch)
Tydzień 9-10:  [████████████████] Monitoring & Deployment (Docker, Prometheus)
Tydzień 11-12: [████████████████] Testing Produkcyjne (Paper → Testnet → Live)
```

---

## BUDŻET SZACUNKOWY

| Kategoria | Koszt Miesięczny |
|-----------|------------------|
| VPS (AWS/GCP Singapore) | $100-200 |
| Exchange Fees (maker 0.02%) | ~$50-100 |
| Data feeds (optional) | $0-50 |
| Monitoring (Grafana Cloud) | $0-50 |
| **RAZEM** | **$150-400/month** |

**Kapitał początkowy:** $5,000-10,000
**Oczekiwany ROI (po optymalizacji):** 5-15% monthly

---

## REKOMENDACJE KOŃCOWE

### DO ZROBIENIA NATYCHMIAST:
1. ✅ Naprawić CORS vulnerability
2. ✅ Dodać asyncio.Lock() do wszystkich shared state
3. ✅ Zaimplementować timeout'y na wszystkie async calls
4. ✅ Stworzyć moduł exchange adapter

### NIE ROBIĆ:
1. ❌ Nie uruchamiać na live z obecnym kodem
2. ❌ Nie używać Mean Reversion strategy (0% win rate)
3. ❌ Nie handlować więcej niż 10% kapitału na pozycję
4. ❌ Nie ignorować alertów kill switch

### PRIORYTETOWE PARY:
1. **AVAX/USDT** - Najwyższy score (184.5)
2. **SOL/USDT** - Wysoka volatility, dobry dla MM
3. **DOGE/USDT** - Najlepszy dla Momentum

---

*Plan wygenerowany: 6 stycznia 2026*
*Następna rewizja: Po zakończeniu Fazy 1*
