import { Server as SocketIOServer } from "socket.io";
import type { Server as HTTPServer } from "http";
import { getDb } from "./db";
import { trades, positions, signals, systemStatus, performance } from "../drizzle/schema";
import { desc } from "drizzle-orm";

export function initWebSocket(httpServer: HTTPServer) {
  const io = new SocketIOServer(httpServer, {
    cors: {
      origin: "*",
      methods: ["GET", "POST"],
    },
    path: "/ws/socket.io",
  });

  io.on("connection", (socket) => {
    console.log(`[WebSocket] Client connected: ${socket.id}`);

    // Send initial data on connection
    sendInitialData(socket);

    // Start real-time updates
    const intervals = startRealTimeUpdates(socket);

    socket.on("disconnect", () => {
      console.log(`[WebSocket] Client disconnected: ${socket.id}`);
      // Clean up intervals
      intervals.forEach(clearInterval);
    });

    // Handle manual data requests
    socket.on("request:trades", async () => {
      const db = await getDb();
      if (!db) return;
      const recentTrades = await db.select().from(trades).orderBy(desc(trades.createdAt)).limit(50);
      socket.emit("trades:update", recentTrades);
    });

    socket.on("request:positions", async () => {
      const db = await getDb();
      if (!db) return;
      const openPositions = await db.select().from(positions);
      socket.emit("positions:update", openPositions);
    });

    socket.on("request:signals", async () => {
      const db = await getDb();
      if (!db) return;
      const recentSignals = await db.select().from(signals).orderBy(desc(signals.createdAt)).limit(20);
      socket.emit("signals:update", recentSignals);
    });
  });

  return io;
}

async function sendInitialData(socket: any) {
  try {
    const db = await getDb();
    if (!db) return;

    // Send system status
    const statusResult = await db.select().from(systemStatus).orderBy(desc(systemStatus.updatedAt)).limit(1);
    socket.emit("system:status", statusResult[0] || null);

    // Send recent trades
    const recentTrades = await db.select().from(trades).orderBy(desc(trades.createdAt)).limit(50);
    socket.emit("trades:update", recentTrades);

    // Send open positions
    const openPositions = await db.select().from(positions);
    socket.emit("positions:update", openPositions);

    // Send recent signals
    const recentSignals = await db.select().from(signals).orderBy(desc(signals.createdAt)).limit(20);
    socket.emit("signals:update", recentSignals);

    // Send performance data
    const performanceResult = await db.select().from(performance).orderBy(desc(performance.createdAt)).limit(1);
    socket.emit("performance:update", performanceResult[0] || null);
  } catch (error) {
    console.error("[WebSocket] Error sending initial data:", error);
  }
}

function startRealTimeUpdates(socket: any): NodeJS.Timeout[] {
  const intervals: NodeJS.Timeout[] = [];

  // Update system status every 1 second
  intervals.push(
    setInterval(async () => {
      try {
        const db = await getDb();
        if (!db) return;
        const statusResult = await db.select().from(systemStatus).orderBy(desc(systemStatus.updatedAt)).limit(1);
        socket.emit("system:status", statusResult[0] || null);
      } catch (error) {
        console.error("[WebSocket] Error updating system status:", error);
      }
    }, 1000)
  );

  // Update trades every 2 seconds
  intervals.push(
    setInterval(async () => {
      try {
        const db = await getDb();
        if (!db) return;
        const recentTrades = await db.select().from(trades).orderBy(desc(trades.createdAt)).limit(50);
        socket.emit("trades:update", recentTrades);
      } catch (error) {
        console.error("[WebSocket] Error updating trades:", error);
      }
    }, 2000)
  );

  // Update positions every 2 seconds
  intervals.push(
    setInterval(async () => {
      try {
        const db = await getDb();
        if (!db) return;
        const openPositions = await db.select().from(positions);
        socket.emit("positions:update", openPositions);
      } catch (error) {
        console.error("[WebSocket] Error updating positions:", error);
      }
    }, 2000)
  );

  // Update signals every 1 second (for live trading)
  intervals.push(
    setInterval(async () => {
      try {
        const db = await getDb();
        if (!db) return;
        const recentSignals = await db.select().from(signals).orderBy(desc(signals.createdAt)).limit(20);
        socket.emit("signals:update", recentSignals);
      } catch (error) {
        console.error("[WebSocket] Error updating signals:", error);
      }
    }, 1000)
  );

  // Update performance every 5 seconds
  intervals.push(
    setInterval(async () => {
      try {
        const db = await getDb();
        if (!db) return;
        const performanceResult = await db.select().from(performance).orderBy(desc(performance.createdAt)).limit(1);
        socket.emit("performance:update", performanceResult[0] || null);
      } catch (error) {
        console.error("[WebSocket] Error updating performance:", error);
      }
    }, 5000)
  );

  return intervals;
}
