import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BarChart3, TrendingUp, Target, Activity, DollarSign } from "lucide-react";
import { Link } from "wouter";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { useMemo } from "react";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function Performance() {
  const { trades, performance, systemStatus, connected } = useWebSocket();

  // Calculate performance metrics
  const metrics = useMemo(() => {
    const closedTrades = trades.filter(t => t.status === "CLOSED");
    const totalTrades = closedTrades.length;
    const winningTrades = closedTrades.filter(t => parseFloat(t.pnl || "0") > 0);
    const losingTrades = closedTrades.filter(t => parseFloat(t.pnl || "0") < 0);
    
    const totalPnl = closedTrades.reduce((sum, t) => sum + parseFloat(t.pnl || "0"), 0);
    const totalWins = winningTrades.reduce((sum, t) => sum + parseFloat(t.pnl || "0"), 0);
    const totalLosses = Math.abs(losingTrades.reduce((sum, t) => sum + parseFloat(t.pnl || "0"), 0));
    
    const winRate = totalTrades > 0 ? (winningTrades.length / totalTrades) * 100 : 0;
    const avgWin = winningTrades.length > 0 ? totalWins / winningTrades.length : 0;
    const avgLoss = losingTrades.length > 0 ? totalLosses / losingTrades.length : 0;
    const profitFactor = totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? 999 : 0;
    
    // Calculate equity curve
    let equity = 10000; // Starting capital
    const equityCurve = closedTrades
      .sort((a, b) => new Date(a.exitTime!).getTime() - new Date(b.exitTime!).getTime())
      .map(trade => {
        equity += parseFloat(trade.pnl || "0");
        return {
          time: new Date(trade.exitTime!).toLocaleDateString(),
          equity: equity,
        };
      });

    return {
      totalTrades,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      winRate,
      totalPnl,
      avgWin,
      avgLoss,
      profitFactor,
      equityCurve,
    };
  }, [trades]);

  // Equity curve chart data
  const chartData = {
    labels: metrics.equityCurve.map(d => d.time),
    datasets: [
      {
        label: "Equity",
        data: metrics.equityCurve.map(d => d.equity),
        borderColor: "rgb(14, 165, 233)",
        backgroundColor: "rgba(14, 165, 233, 0.1)",
        fill: true,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 6,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        mode: "index" as const,
        intersect: false,
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        titleColor: "#fff",
        bodyColor: "#fff",
        borderColor: "rgb(14, 165, 233)",
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        grid: {
          color: "rgba(255, 255, 255, 0.05)",
        },
        ticks: {
          color: "rgba(255, 255, 255, 0.5)",
          maxRotation: 45,
          minRotation: 45,
        },
      },
      y: {
        grid: {
          color: "rgba(255, 255, 255, 0.05)",
        },
        ticks: {
          color: "rgba(255, 255, 255, 0.5)",
          callback: function(value: any) {
            return "$" + value.toLocaleString();
          },
        },
      },
    },
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container py-4">
          <div className="flex items-center justify-between">
            <Link href="/">
              <div className="flex items-center gap-3 cursor-pointer hover:opacity-80 transition-opacity">
                <BarChart3 className="w-8 h-8 text-primary" />
                <div>
                  <h1 className="text-2xl font-bold gradient-text">QUANTUM HFT</h1>
                  <p className="text-sm text-muted-foreground">Performance Analytics</p>
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
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total P&L</CardTitle>
              <DollarSign className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${metrics.totalPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                {metrics.totalPnl >= 0 ? "+" : ""}${metrics.totalPnl.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">All time</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Win Rate</CardTitle>
              <Target className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{metrics.winRate.toFixed(1)}%</div>
              <p className="text-xs text-muted-foreground mt-1">
                {metrics.winningTrades}W / {metrics.losingTrades}L
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Profit Factor</CardTitle>
              <TrendingUp className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-primary">
                {metrics.profitFactor > 999 ? "∞" : metrics.profitFactor.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Wins / Losses</p>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Trades</CardTitle>
              <Activity className="w-4 h-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{metrics.totalTrades}</div>
              <p className="text-xs text-muted-foreground mt-1">Closed positions</p>
            </CardContent>
          </Card>
        </div>

        {/* Equity Curve */}
        <Card className="bg-card/50 backdrop-blur-sm border-border mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              Equity Curve
            </CardTitle>
          </CardHeader>
          <CardContent>
            {metrics.equityCurve.length > 0 ? (
              <div style={{ height: "400px" }}>
                <Line data={chartData} options={chartOptions} />
              </div>
            ) : (
              <div className="text-center py-20 text-muted-foreground">
                <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No trading data available</p>
                <p className="text-sm mt-2">Start trading to see your equity curve</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Detailed Statistics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader>
              <CardTitle>Trade Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Average Win</span>
                <span className="font-mono font-bold text-green-500">+${metrics.avgWin.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Average Loss</span>
                <span className="font-mono font-bold text-red-500">-${metrics.avgLoss.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Winning Trades</span>
                <span className="font-mono font-bold">{metrics.winningTrades}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Losing Trades</span>
                <span className="font-mono font-bold">{metrics.losingTrades}</span>
              </div>
              <div className="flex justify-between items-center pt-3 border-t border-border">
                <span className="text-muted-foreground">Total Trades</span>
                <span className="font-mono font-bold text-primary">{metrics.totalTrades}</span>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 backdrop-blur-sm border-border">
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Win Rate</span>
                <span className="font-mono font-bold text-primary">{metrics.winRate.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Profit Factor</span>
                <span className="font-mono font-bold text-primary">
                  {metrics.profitFactor > 999 ? "∞" : metrics.profitFactor.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Sharpe Ratio</span>
                <span className="font-mono font-bold">
                  {performance?.sharpeRatio ? parseFloat(performance.sharpeRatio).toFixed(2) : "N/A"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Max Drawdown</span>
                <span className="font-mono font-bold text-red-500">
                  {performance?.maxDrawdown ? parseFloat(performance.maxDrawdown).toFixed(2) + "%" : "N/A"}
                </span>
              </div>
              <div className="flex justify-between items-center pt-3 border-t border-border">
                <span className="text-muted-foreground">Total P&L</span>
                <span className={`font-mono font-bold ${metrics.totalPnl >= 0 ? "text-green-500" : "text-red-500"}`}>
                  {metrics.totalPnl >= 0 ? "+" : ""}${metrics.totalPnl.toFixed(2)}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
