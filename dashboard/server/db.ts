import { eq, desc, and, gte, lte, sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/mysql2";
import mysql from "mysql2/promise";
import * as schema from "../drizzle/schema";
import { 
  InsertUser, users, trades, positions, signals, performance, 
  systemStatus, aiInsights, Trade, Position, Signal 
} from "../drizzle/schema";
import { ENV } from './_core/env';

let _db: any = null;

export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      const pool = mysql.createPool(process.env.DATABASE_URL);
      _db = drizzle(pool, { schema, mode: "default" });
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      openId: user.openId,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "email", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values).onDuplicateKeyUpdate({
      set: updateSet,
    });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

// Trading data helpers
export async function getRecentTrades(userId: number, limit: number = 50): Promise<Trade[]> {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(trades)
    .where(eq(trades.userId, userId))
    .orderBy(desc(trades.createdAt))
    .limit(limit);
}

export async function getOpenPositions(userId: number): Promise<Position[]> {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(positions)
    .where(eq(positions.userId, userId))
    .orderBy(desc(positions.updatedAt));
}

export async function getPendingSignals(userId: number): Promise<Signal[]> {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(signals)
    .where(and(
      eq(signals.userId, userId),
      eq(signals.status, "PENDING")
    ))
    .orderBy(desc(signals.createdAt))
    .limit(20);
}

export async function getPerformanceData(userId: number, days: number = 30) {
  const db = await getDb();
  if (!db) return [];
  
  const cutoff = Date.now() - (days * 24 * 60 * 60 * 1000);
  
  return db.select().from(performance)
    .where(and(
      eq(performance.userId, userId),
      gte(performance.timestamp, cutoff)
    ))
    .orderBy(performance.timestamp);
}

export async function getSystemStatus(userId: number) {
  const db = await getDb();
  if (!db) return null;
  
  const result = await db.select().from(systemStatus)
    .where(eq(systemStatus.userId, userId))
    .limit(1);
    
  return result.length > 0 ? result[0] : null;
}

export async function getAIInsights(userId: number, limit: number = 10) {
  const db = await getDb();
  if (!db) return [];
  
  return db.select().from(aiInsights)
    .where(eq(aiInsights.userId, userId))
    .orderBy(desc(aiInsights.createdAt))
    .limit(limit);
}

export async function getTradeStats(userId: number, days: number = 30) {
  const db = await getDb();
  if (!db) return null;
  
  const cutoff = new Date(Date.now() - (days * 24 * 60 * 60 * 1000));
  
  const result = await db.select({
    totalTrades: sql<number>`COUNT(*)`,
    winningTrades: sql<number>`SUM(CASE WHEN ${trades.pnl} > 0 THEN 1 ELSE 0 END)`,
    losingTrades: sql<number>`SUM(CASE WHEN ${trades.pnl} < 0 THEN 1 ELSE 0 END)`,
    totalPnl: sql<number>`SUM(${trades.pnl})`,
    avgWin: sql<number>`AVG(CASE WHEN ${trades.pnl} > 0 THEN ${trades.pnl} ELSE NULL END)`,
    avgLoss: sql<number>`AVG(CASE WHEN ${trades.pnl} < 0 THEN ${trades.pnl} ELSE NULL END)`,
  }).from(trades)
    .where(and(
      eq(trades.userId, userId),
      eq(trades.status, "CLOSED"),
      gte(trades.exitTime, cutoff)
    ));
    
  return result[0] || null;
}
