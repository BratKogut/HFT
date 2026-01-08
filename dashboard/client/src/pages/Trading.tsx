import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, TrendingUp, TrendingDown, Zap, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { Link } from "wouter";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useState } from "react";

export default function Trading() {
  const { signals, positions, systemStatus, connected } = useWebSocket();
  const [selectedSignal, setSelectedSignal] = useState<any>(null);

  const pendingSignals = signals.filter(s => s.status === "PENDING");

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <Link href="/">
              <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
                <Activity className="w-8 h-8 text-primary" />
                <div>
                  <h1 className="text-2xl font-bold gradient-text">QUANTUM HFT</h1>
                  <p className="text-sm text-muted-foreground">Trading Interface</p>
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Live Signals */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="bg-card/50 backdrop-blur-sm border-border">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Zap className="w-5 h-5 text-primary" />
                    Live Signals
                  </CardTitle>
                  <Badge variant="outline" className="font-mono">
                    {pendingSignals.length} Active
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                {pendingSignals.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No active signals</p>
                    <p className="text-sm mt-2">Waiting for trading opportunities...</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {pendingSignals.map((signal) => (
                      <div
                        key={signal.id}
                        className={`p-4 rounded-lg border transition-all cursor-pointer ${
                          selectedSignal?.id === signal.id
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50"
                        }`}
                        onClick={() => setSelectedSignal(signal)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                                signal.side === "LONG"
                                  ? "bg-green-500/10 text-green-500"
                                  : "bg-red-500/10 text-red-500"
                              }`}
                            >
                              {signal.side === "LONG" ? (
                                <ArrowUpRight className="w-5 h-5" />
                              ) : (
                                <ArrowDownRight className="w-5 h-5" />
                              )}
                            </div>
                            <div>
                              <div className="font-bold text-lg">{signal.symbol}</div>
                              <div className="text-sm text-muted-foreground">
                                {new Date(signal.createdAt).toLocaleTimeString()}
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm text-muted-foreground">Entry Price</div>
                            <div className="font-mono font-bold">${parseFloat(signal.price).toFixed(2)}</div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between mt-3 pt-3 border-t border-border">
                          <div className="flex items-center gap-4 text-sm">
                            <div>
                              <span className="text-muted-foreground">Confidence: </span>
                              <span className="font-bold text-primary">
                                {(parseFloat(signal.confidence) * 100).toFixed(1)}%
                              </span>
                            </div>
                            <Badge variant="outline" className={signal.side === "LONG" ? "text-green-500" : "text-red-500"}>
                              {signal.side}
                            </Badge>
                          </div>
                          <Button
                            size="sm"
                            className={signal.side === "LONG" ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"}
                            onClick={(e) => {
                              e.stopPropagation();
                              // TODO: Execute trade
                              console.log("Execute trade:", signal);
                            }}
                          >
                            Execute
                          </Button>
                        </div>
                        {signal.reason && (
                          <div className="mt-3 pt-3 border-t border-border text-sm text-muted-foreground">
                            <span className="font-medium">Reason:</span> {signal.reason}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Open Positions */}
            <Card className="bg-card/50 backdrop-blur-sm border-border">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-primary" />
                  Open Positions
                </CardTitle>
              </CardHeader>
              <CardContent>
                {positions.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <TrendingUp className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No open positions</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {positions.map((position) => {
                      const pnl = parseFloat(position.unrealizedPnl);
                      const pnlPct = parseFloat(position.unrealizedPnlPct);
                      const isProfitable = pnl >= 0;

                      return (
                        <div
                          key={position.id}
                          className="p-4 rounded-lg border border-border hover:border-primary/50 transition-colors"
                        >
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <div
                                className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                                  position.side === "LONG"
                                    ? "bg-green-500/10 text-green-500"
                                    : "bg-red-500/10 text-red-500"
                                }`}
                              >
                                {position.side === "LONG" ? (
                                  <TrendingUp className="w-5 h-5" />
                                ) : (
                                  <TrendingDown className="w-5 h-5" />
                                )}
                              </div>
                              <div>
                                <div className="font-bold text-lg">{position.symbol}</div>
                                <Badge variant="outline" className={position.side === "LONG" ? "text-green-500" : "text-red-500"}>
                                  {position.side}
                                </Badge>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className={`text-2xl font-bold ${isProfitable ? "text-green-500" : "text-red-500"}`}>
                                {isProfitable ? "+" : ""}${pnl.toFixed(2)}
                              </div>
                              <div className={`text-sm ${isProfitable ? "text-green-500" : "text-red-500"}`}>
                                {isProfitable ? "+" : ""}{pnlPct.toFixed(2)}%
                              </div>
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                              <div className="text-muted-foreground">Entry</div>
                              <div className="font-mono font-bold">${parseFloat(position.entryPrice).toFixed(2)}</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground">Current</div>
                              <div className="font-mono font-bold">${parseFloat(position.currentPrice).toFixed(2)}</div>
                            </div>
                            <div>
                              <div className="text-muted-foreground">Size</div>
                              <div className="font-mono font-bold">{parseFloat(position.size).toFixed(4)}</div>
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
                          <div className="mt-3 pt-3 border-t border-border">
                            <Button variant="destructive" size="sm" className="w-full">
                              Close Position
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column - Market Info & Controls */}
          <div className="space-y-6">
            <Card className="bg-card/50 backdrop-blur-sm border-border">
              <CardHeader>
                <CardTitle className="text-lg">System Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Mode</div>
                  <Badge variant={systemStatus?.mode === "LIVE" ? "default" : "secondary"} className="text-sm">
                    {systemStatus?.mode || "PAPER"}
                  </Badge>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Status</div>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${systemStatus?.isActive ? 'bg-green-500' : 'bg-gray-500'} animate-pulse`} />
                    <span className="font-medium">{systemStatus?.isActive ? "Active" : "Inactive"}</span>
                  </div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Signals Generated</div>
                  <div className="font-mono font-bold text-lg">{systemStatus?.signalsGenerated || 0}</div>
                </div>
                <div>
                  <div className="text-sm text-muted-foreground mb-1">Trades Executed</div>
                  <div className="font-mono font-bold text-lg">{systemStatus?.tradesExecuted || 0}</div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card/50 backdrop-blur-sm border-border">
              <CardHeader>
                <CardTitle className="text-lg">Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button className="w-full" variant="outline">
                  Close All Positions
                </Button>
                <Button className="w-full" variant="outline">
                  Pause Trading
                </Button>
                <Link href="/">
                  <Button className="w-full" variant="secondary">
                    Back to Dashboard
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
