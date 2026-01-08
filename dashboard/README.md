# Quantum HFT Dashboard

Real-time monitoring dashboard for High-Frequency Trading system with WebSocket streaming, risk management, and performance analytics.

## 🚀 Features

- **Real-time WebSocket Streaming** - Live updates with <100ms latency
- **Trading Interface** - Live signals, position monitoring, one-click execution
- **Risk Management** - DRB-Guard monitoring, drawdown tracking, exposure analysis
- **Performance Analytics** - Equity curve, profit factor, Sharpe ratio, win rate
- **Trade Log** - Complete trade history with detailed P&L breakdown
- **Professional UI** - Deep Space theme with Electric Blue accents

## 🛠️ Tech Stack

- **Frontend**: React 19, TypeScript, TailwindCSS 4, shadcn/ui
- **Backend**: Express, Socket.io, tRPC 11
- **Database**: MySQL with Drizzle ORM
- **Charts**: Chart.js for equity curve visualization
- **Real-time**: WebSocket with Socket.io

## 📦 Installation

```bash
cd dashboard
pnpm install
```

## 🔧 Configuration

Create `.env` file with:

```env
DATABASE_URL=mysql://user:password@host:port/database
JWT_SECRET=your-secret-key
VITE_APP_ID=your-app-id
```

## 🚀 Development

```bash
# Start development server
pnpm dev

# Push database schema
pnpm db:push

# Run tests
pnpm test
```

## 📊 Database Schema

- **trades** - Trade history with entry/exit prices and P&L
- **positions** - Open positions with real-time unrealized P&L
- **signals** - Trading signals with confidence scores
- **performance** - Performance metrics (Sharpe ratio, drawdown)
- **systemStatus** - System health and statistics
- **aiInsights** - AI-generated trade analysis
- **users** - User authentication and profiles

## 🔗 Integration with HFT Backend

The dashboard connects to the HFT Python backend via WebSocket. To integrate:

1. Update WebSocket server in `server/websocket.ts` to fetch data from your HFT system
2. Configure database connection to match your HFT database
3. Adjust data streaming intervals based on your needs

## 📱 Pages

- **Home** (`/`) - Overview dashboard with quick stats
- **Trading** (`/trading`) - Live signals and position management
- **Risk Management** (`/risk`) - DRB-Guard and risk metrics
- **Performance** (`/performance`) - Analytics and equity curve
- **Trade Log** (`/trade-log`) - Complete trade history

## 🎨 Customization

- Theme colors: `client/src/index.css`
- WebSocket intervals: `server/websocket.ts`
- Database schema: `drizzle/schema.ts`

## 📝 License

Part of the Quantum HFT project.
