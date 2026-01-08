import { useEffect, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";

interface SystemStatus {
  id: number;
  userId: number;
  isActive: boolean;
  mode: "PAPER" | "LIVE";
  lastHeartbeat: Date;
  ticksProcessed: number;
  signalsGenerated: number;
  tradesExecuted: number;
  updatedAt: Date;
}

interface Trade {
  id: number;
  userId: number;
  symbol: string;
  side: "LONG" | "SHORT";
  entryPrice: string;
  exitPrice: string | null;
  size: string;
  pnl: string | null;
  pnlPct: string | null;
  fees: string;
  exitReason: string | null;
  confidence: string | null;
  status: "OPEN" | "CLOSED";
  entryTime: Date;
  exitTime: Date | null;
  createdAt: Date;
}

interface Position {
  id: number;
  userId: number;
  symbol: string;
  side: "LONG" | "SHORT";
  entryPrice: string;
  currentPrice: string;
  size: string;
  unrealizedPnl: string;
  unrealizedPnlPct: string;
  takeProfit: string | null;
  stopLoss: string | null;
  entryTime: Date;
  updatedAt: Date;
}

interface Signal {
  id: number;
  userId: number;
  symbol: string;
  side: "LONG" | "SHORT";
  confidence: string;
  price: string;
  reason: string | null;
  status: "PENDING" | "EXECUTED" | "REJECTED" | "EXPIRED";
  createdAt: Date;
}

interface Performance {
  id: number;
  userId: number;
  timestamp: number;
  equity: string;
  dailyPnl: string;
  dailyPnlPct: string;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: string;
  profitFactor: string | null;
  sharpeRatio: string | null;
  maxDrawdown: string | null;
  createdAt: Date;
}

interface WebSocketData {
  systemStatus: SystemStatus | null;
  trades: Trade[];
  positions: Position[];
  signals: Signal[];
  performance: Performance | null;
  connected: boolean;
}

export function useWebSocket() {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [data, setData] = useState<WebSocketData>({
    systemStatus: null,
    trades: [],
    positions: [],
    signals: [],
    performance: null,
    connected: false,
  });

  useEffect(() => {
    // Connect to WebSocket server
    const socketInstance = io({
      path: "/ws/socket.io",
      transports: ["websocket", "polling"],
    });

    socketInstance.on("connect", () => {
      console.log("[WebSocket] Connected");
      setData((prev) => ({ ...prev, connected: true }));
    });

    socketInstance.on("disconnect", () => {
      console.log("[WebSocket] Disconnected");
      setData((prev) => ({ ...prev, connected: false }));
    });

    // Listen for system status updates
    socketInstance.on("system:status", (status: SystemStatus) => {
      setData((prev) => ({ ...prev, systemStatus: status }));
    });

    // Listen for trades updates
    socketInstance.on("trades:update", (trades: Trade[]) => {
      setData((prev) => ({ ...prev, trades }));
    });

    // Listen for positions updates
    socketInstance.on("positions:update", (positions: Position[]) => {
      setData((prev) => ({ ...prev, positions }));
    });

    // Listen for signals updates
    socketInstance.on("signals:update", (signals: Signal[]) => {
      setData((prev) => ({ ...prev, signals }));
    });

    // Listen for performance updates
    socketInstance.on("performance:update", (performance: Performance) => {
      setData((prev) => ({ ...prev, performance }));
    });

    setSocket(socketInstance);

    return () => {
      socketInstance.disconnect();
    };
  }, []);

  const requestTrades = useCallback(() => {
    socket?.emit("request:trades");
  }, [socket]);

  const requestPositions = useCallback(() => {
    socket?.emit("request:positions");
  }, [socket]);

  const requestSignals = useCallback(() => {
    socket?.emit("request:signals");
  }, [socket]);

  return {
    ...data,
    requestTrades,
    requestPositions,
    requestSignals,
  };
}
