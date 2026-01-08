import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollText, TrendingUp, TrendingDown } from "lucide-react";
import { Link } from "wouter";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function TradeLog() {
  const { trades, systemStatus, connected } = useWebSocket();

  const closedTrades = trades
    .filter(t => t.status === "CLOSED")
    .sort((a, b) => new Date(b.exitTime!).getTime() - new Date(a.exitTime!).getTime());

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <Link href="/">
              <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
                <ScrollText className="w-8 h-8 text-primary" />
                <div>
                  <h1 className="text-2xl font-bold gradient-text">QUANTUM HFT</h1>
                  <p className="text-sm text-muted-foreground">Trade Log</p>
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
        <Card className="bg-card/50 backdrop-blur-sm border-border">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <ScrollText className="w-5 h-5 text-primary" />
                Complete Trade History
              </CardTitle>
              <Badge variant="outline" className="font-mono">
                {closedTrades.length} Trades
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {closedTrades.length === 0 ? (
              <div className="text-center py-20 text-muted-foreground">
                <ScrollText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No closed trades</p>
                <p className="text-sm mt-2">Your trade history will appear here</p>
              </div>
            ) : (
              <div className="space-y-3">
                {closedTrades.map((trade) => {
                  const pnl = parseFloat(trade.pnl || "0");
                  const isProfitable = pnl >= 0;
                  const duration = trade.exitTime && trade.entryTime
                    ? Math.floor((new Date(trade.exitTime).getTime() - new Date(trade.entryTime).getTime()) / 1000)
                    : 0;
                  const durationStr = duration > 3600
                    ? `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`
                    : duration > 60
                    ? `${Math.floor(duration / 60)}m ${duration % 60}s`
                    : `${duration}s`;

                  return (
                    <div
                      key={trade.id}
                      className="p-4 rounded-lg border border-border hover:border-primary/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                              trade.side === "LONG"
                                ? "bg-green-500/10 text-green-500"
                                : "bg-red-500/10 text-red-500"
                            }`}
                          >
                            {trade.side === "LONG" ? (
                              <TrendingUp className="w-5 h-5" />
                            ) : (
                              <TrendingDown className="w-5 h-5" />
                            )}
                          </div>
                          <div>
                            <div className="font-bold text-lg">{trade.symbol}</div>
                            <div className="text-sm text-muted-foreground">
                              {new Date(trade.exitTime!).toLocaleString()}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-bold ${isProfitable ? "text-green-500" : "text-red-500"}`}>
                            {isProfitable ? "+" : ""}${pnl.toFixed(2)}
                          </div>
                          <Badge variant={isProfitable ? "default" : "destructive"} className="mt-1">
                            {trade.side}
                          </Badge>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <div className="text-muted-foreground">Entry Price</div>
                          <div className="font-mono font-bold">${parseFloat(trade.entryPrice).toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Exit Price</div>
                          <div className="font-mono font-bold">${parseFloat(trade.exitPrice || "0").toFixed(2)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Size</div>
                          <div className="font-mono font-bold">{parseFloat(trade.size).toFixed(4)}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Duration</div>
                          <div className="font-mono font-bold">{durationStr}</div>
                        </div>
                      </div>
                      {trade.exitReason && (
                        <div className="mt-3 pt-3 border-t border-border text-sm">
                          <span className="text-muted-foreground">Exit Reason:</span>{" "}
                          <span className="font-medium">{trade.exitReason}</span>
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
