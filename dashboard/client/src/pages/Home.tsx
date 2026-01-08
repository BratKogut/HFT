import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, BarChart3, Shield, TrendingDown, Zap, Target } from "lucide-react";
import { Link } from "wouter";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useEffect, useState } from "react";

export default function Home() {
  const { systemStatus, trades, positions, performance, connected } = useWebSocket();
  const [unrealizedPnl, setUnrealizedPnl] = useState(0);

  useEffect(() => {
    // Calculate total unrealized P&L from positions
    if (positions.length > 0) {
      const total = positions.reduce((sum, pos) => sum + parseFloat(pos.unrealizedPnl || "0"), 0);
      setUnrealizedPnl(total);
    }
  }, [positions]);

  // Calculate stats from trades
  const closedTrades = trades.filter(t => t.status === "CLOSED");
  const totalTrades = closedTrades.length;
  const winningTrades = closedTrades.filter(t => parseFloat(t.pnl || "0") > 0).length;
  const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
  const totalPnl = closedTrades.reduce((sum, t) => sum + parseFloat(t.pnl || "0"), 0);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap className="w-8 h-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold gradient-text">QUANTUM HFT</h1>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <div className={`w-2 h-2 rounded-full ${systemStatus?.isActive ? 'bg-green-500' : 'bg-gray-500'} animate-pulse`} />
                    <span className="font-medium">{systemStatus?.isActive ? 'ACTIVE' : 'INACTIVE'}</span>
                  </div>
                  <span>•</span>
                  <Badge variant={systemStatus?.mode === "LIVE" ? "default" : "secondary"} className="text-xs">
                    {systemStatus?.mode || "PAPER"}
                  </Badge>
                  {connected && (
                    <>
                      <span>•</span>
                      <div className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                        <span className="text-xs">Live</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-muted-foreground">Unrealized P&L</div>
              <div className={`text-2xl font-bold ${unrealizedPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${unrealizedPnl.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="container py-8">
        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-colors">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Trades</CardTitle>
              <Activity className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{totalTrades}</div>
              <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-colors">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Win Rate</CardTitle>
              <Target className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {totalTrades > 0 ? `${winRate.toFixed(1)}%` : "NaN%"}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {winningTrades}W / {totalTrades - winningTrades}L
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-colors">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total P&L</CardTitle>
              <TrendingDown className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${totalPnl.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-colors">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Open Positions</CardTitle>
              <BarChart3 className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{positions.length}</div>
              <p className="text-xs text-muted-foreground mt-1">Active trades</p>
            </CardContent>
          </Card>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Link href="/trading">
            <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-all hover:scale-105 cursor-pointer group">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                  <Activity className="w-6 h-6 text-primary" />
                </div>
                <CardTitle className="text-lg">Trading</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Live signals, order execution, and market monitoring
                </p>
              </CardContent>
            </Card>
          </Link>

          <Link href="/risk">
            <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-all hover:scale-105 cursor-pointer group">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                  <Shield className="w-6 h-6 text-primary" />
                </div>
                <CardTitle className="text-lg">Risk Management</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Drawdown monitoring, position limits, and DRB-Guard status
                </p>
              </CardContent>
            </Card>
          </Link>

          <Link href="/performance">
            <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-all hover:scale-105 cursor-pointer group">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                  <BarChart3 className="w-6 h-6 text-primary" />
                </div>
                <CardTitle className="text-lg">Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Equity curve, analytics, and performance heatmaps
                </p>
              </CardContent>
            </Card>
          </Link>

          <Link href="/trade-log">
            <Card className="bg-card/50 backdrop-blur-sm border-border hover:border-primary/50 transition-all hover:scale-105 cursor-pointer group">
              <CardHeader>
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                  <TrendingDown className="w-6 h-6 text-primary" />
                </div>
                <CardTitle className="text-lg">Trade Log</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Complete trade history with detailed P&L breakdown
                </p>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* System Info */}
        {systemStatus && (
          <Card className="mt-8 bg-card/50 backdrop-blur-sm border-border">
            <CardHeader>
              <CardTitle className="text-lg">System Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Ticks Processed</div>
                  <div className="font-mono font-bold">{systemStatus.ticksProcessed.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Signals Generated</div>
                  <div className="font-mono font-bold">{systemStatus.signalsGenerated}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Trades Executed</div>
                  <div className="font-mono font-bold">{systemStatus.tradesExecuted}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Last Heartbeat</div>
                  <div className="font-mono text-xs">{new Date(systemStatus.lastHeartbeat).toLocaleTimeString()}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
