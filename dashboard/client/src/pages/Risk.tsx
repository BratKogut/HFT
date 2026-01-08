import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Shield, AlertTriangle, TrendingDown, Activity, DollarSign } from "lucide-react";
import { Link } from "wouter";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useMemo } from "react";

export default function Risk() {
  const { positions, trades, systemStatus, connected } = useWebSocket();

  // Calculate risk metrics
  const riskMetrics = useMemo(() => {
    // Calculate total exposure
    const totalExposure = positions.reduce((sum, pos) => {
      return sum + Math.abs(parseFloat(pos.size) * parseFloat(pos.currentPrice));
    }, 0);

    // Calculate unrealized P&L
    const unrealizedPnl = positions.reduce((sum, pos) => sum + parseFloat(pos.unrealizedPnl), 0);

    // Calculate drawdown from recent trades
    const closedTrades = trades.filter(t => t.status === "CLOSED");
    let peak = 10000; // Starting capital
    let maxDrawdown = 0;
    let currentEquity = 10000;

    closedTrades
      .sort((a, b) => new Date(a.exitTime!).getTime() - new Date(b.exitTime!).getTime())
      .forEach(trade => {
        currentEquity += parseFloat(trade.pnl || "0");
        if (currentEquity > peak) {
          peak = currentEquity;
        }
        const drawdown = ((peak - currentEquity) / peak) * 100;
        if (drawdown > maxDrawdown) {
          maxDrawdown = drawdown;
        }
      });

    // Risk level based on drawdown
    let riskLevel: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" = "LOW";
    if (maxDrawdown > 20) riskLevel = "CRITICAL";
    else if (maxDrawdown > 15) riskLevel = "HIGH";
    else if (maxDrawdown > 10) riskLevel = "MEDIUM";

    return {
      totalExposure,
      unrealizedPnl,
      maxDrawdown,
      currentDrawdown: maxDrawdown,
      riskLevel,
      openPositions: positions.length,
    };
  }, [positions, trades]);

  const getRiskColor = (level: string) => {
    switch (level) {
      case "LOW": return "text-green-500";
      case "MEDIUM": return "text-yellow-500";
      case "HIGH": return "text-orange-500";
      case "CRITICAL": return "text-red-500";
      default: return "text-gray-500";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <Link href="/">
              <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
                <Shield className="w-8 h-8 text-primary" />
                <div>
                  <h1 className="text-2xl font-bold gradient-text">QUANTUM HFT</h1>
                  <p className="text-sm text-muted-foreground">Risk Management</p>
                </div>
              </div>
            </Link>
            <div className="flex items-center gap-4">
              {connected && (
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-muted-foreground">Live</span>
                </div>
              )}
              <Badge variant={systemStatus?.mode === "LIVE" ? "default" : "secondary"}>
                {systemStatus?.mode || "PAPER"}
              </Badge>
            </div>
          </div>
        </div>
      </header>

      <main className="container py-8">
        {/* Risk Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Risk Level</CardTitle>
              <AlertTriangle className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${getRiskColor(riskMetrics.riskLevel)}`}>
                {riskMetrics.riskLevel}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Current status</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Max Drawdown</CardTitle>
              <TrendingDown className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-red-500">
                {riskMetrics.maxDrawdown.toFixed(2)}%
              </div>
              <p className="text-xs text-muted-foreground mt-1">All time</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Exposure</CardTitle>
              <DollarSign className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">${riskMetrics.totalExposure.toFixed(2)}</div>
              <p className="text-xs text-muted-foreground mt-1">Open positions</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Unrealized P&L</CardTitle>
              <Activity className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${riskMetrics.unrealizedPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                {riskMetrics.unrealizedPnl >= 0 ? "+" : ""}${riskMetrics.unrealizedPnl.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Current positions</p>
            </CardContent>
          </Card>
        </div>

        {/* DRB-Guard Status */}
        <Card className="bg-card/50 backdrop-blur-sm border-border mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" />
              DRB-Guard Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center p-6 rounded-lg bg-green-500/10 border border-green-500/20">
                <div className="text-4xl font-bold text-green-500 mb-2">ACTIVE</div>
                <div className="text-sm text-muted-foreground">Protection Status</div>
              </div>
              <div className="text-center p-6 rounded-lg bg-primary/10 border border-primary/20">
                <div className="text-4xl font-bold text-primary mb-2">{riskMetrics.maxDrawdown.toFixed(1)}%</div>
                <div className="text-sm text-muted-foreground">Current Drawdown</div>
              </div>
              <div className="text-center p-6 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                <div className="text-4xl font-bold text-yellow-500 mb-2">20.0%</div>
                <div className="text-sm text-muted-foreground">Drawdown Limit</div>
              </div>
            </div>
            <div className="mt-6 p-4 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">
                <strong>DRB-Guard (Drawdown Risk Breaker)</strong> monitors your account drawdown in real-time. 
                Trading will be automatically halted if drawdown exceeds 20% to protect your capital.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Position Risk Analysis */}
        <Card className="bg-card/50 backdrop-blur-sm border-border">
          <CardHeader>
            <CardTitle>Position Risk Analysis</CardTitle>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Shield className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No open positions</p>
                <p className="text-sm mt-2">Risk metrics will appear when you have active trades</p>
              </div>
            ) : (
              <div className="space-y-4">
                {positions.map((position) => {
                  const pnl = parseFloat(position.unrealizedPnl);
                  const pnlPct = parseFloat(position.unrealizedPnlPct);
                  const exposure = Math.abs(parseFloat(position.size) * parseFloat(position.currentPrice));
                  const isProfitable = pnl >= 0;

                  return (
                    <div
                      key={position.id}
                      className="p-4 rounded-lg border border-border hover:border-primary/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <div className="font-bold text-lg">{position.symbol}</div>
                          <Badge variant="outline" className={position.side === "LONG" ? "text-green-500" : "text-red-500"}>
                            {position.side}
                          </Badge>
                        </div>
                        <div className="text-right">
                          <div className={`text-xl font-bold ${isProfitable ? "text-green-500" : "text-red-500"}`}>
                            {isProfitable ? "+" : ""}${pnl.toFixed(2)}
                          </div>
                          <div className={`text-sm ${isProfitable ? "text-green-500" : "text-red-500"}`}>
                            {isProfitable ? "+" : ""}{pnlPct.toFixed(2)}%
                          </div>
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <div className="text-muted-foreground">Exposure</div>
                          <div className="font-mono font-bold">${exposure.toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Size</div>
                          <div className="font-mono font-bold">{parseFloat(position.size).toFixed(4)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Entry</div>
                          <div className="font-mono font-bold">${parseFloat(position.entryPrice).toFixed(2)}</div>
                        </div>
                      </div>
                      {(position.takeProfit || position.stopLoss) && (
                        <div className="grid grid-cols-2 gap-4 mt-3 pt-3 border-t border-border text-sm">
                          {position.takeProfit && (
                            <div>
                              <div className="text-muted-foreground">Take Profit</div>
                              <div className="font-mono text-green-500">${parseFloat(position.takeProfit).toFixed(2)}</div>
                            </div>
                          )}
                          {position.stopLoss && (
                            <div>
                              <div className="text-muted-foreground">Stop Loss</div>
                              <div className="font-mono text-red-500">${parseFloat(position.stopLoss).toFixed(2)}</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
