import { int, mysqlEnum, mysqlTable, text, timestamp, varchar, decimal, boolean, bigint } from "drizzle-orm/mysql-core";

export const users = mysqlTable("users", {
  id: int("id").autoincrement().primaryKey(),
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export const trades = mysqlTable("trades", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  symbol: varchar("symbol", { length: 20 }).notNull(),
  side: mysqlEnum("side", ["LONG", "SHORT"]).notNull(),
  entryPrice: decimal("entryPrice", { precision: 20, scale: 8 }).notNull(),
  exitPrice: decimal("exitPrice", { precision: 20, scale: 8 }),
  size: decimal("size", { precision: 20, scale: 8 }).notNull(),
  pnl: decimal("pnl", { precision: 20, scale: 8 }),
  pnlPct: decimal("pnlPct", { precision: 10, scale: 4 }),
  fees: decimal("fees", { precision: 20, scale: 8 }).default("0"),
  exitReason: varchar("exitReason", { length: 50 }),
  confidence: decimal("confidence", { precision: 5, scale: 4 }),
  status: mysqlEnum("status", ["OPEN", "CLOSED"]).default("OPEN").notNull(),
  entryTime: timestamp("entryTime").notNull(),
  exitTime: timestamp("exitTime"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export const positions = mysqlTable("positions", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  symbol: varchar("symbol", { length: 20 }).notNull(),
  side: mysqlEnum("side", ["LONG", "SHORT"]).notNull(),
  entryPrice: decimal("entryPrice", { precision: 20, scale: 8 }).notNull(),
  currentPrice: decimal("currentPrice", { precision: 20, scale: 8 }).notNull(),
  size: decimal("size", { precision: 20, scale: 8 }).notNull(),
  unrealizedPnl: decimal("unrealizedPnl", { precision: 20, scale: 8 }).notNull(),
  unrealizedPnlPct: decimal("unrealizedPnlPct", { precision: 10, scale: 4 }).notNull(),
  takeProfit: decimal("takeProfit", { precision: 20, scale: 8 }),
  stopLoss: decimal("stopLoss", { precision: 20, scale: 8 }),
  entryTime: timestamp("entryTime").notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export const signals = mysqlTable("signals", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  symbol: varchar("symbol", { length: 20 }).notNull(),
  side: mysqlEnum("side", ["LONG", "SHORT"]).notNull(),
  confidence: decimal("confidence", { precision: 5, scale: 4 }).notNull(),
  price: decimal("price", { precision: 20, scale: 8 }).notNull(),
  reason: text("reason"),
  status: mysqlEnum("status", ["PENDING", "EXECUTED", "REJECTED", "EXPIRED"]).default("PENDING").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export const performance = mysqlTable("performance", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  timestamp: bigint("timestamp", { mode: "number" }).notNull(),
  equity: decimal("equity", { precision: 20, scale: 8 }).notNull(),
  dailyPnl: decimal("dailyPnl", { precision: 20, scale: 8 }).notNull(),
  dailyPnlPct: decimal("dailyPnlPct", { precision: 10, scale: 4 }).notNull(),
  totalTrades: int("totalTrades").notNull(),
  winningTrades: int("winningTrades").notNull(),
  losingTrades: int("losingTrades").notNull(),
  winRate: decimal("winRate", { precision: 5, scale: 4 }).notNull(),
  profitFactor: decimal("profitFactor", { precision: 10, scale: 4 }),
  sharpeRatio: decimal("sharpeRatio", { precision: 10, scale: 4 }),
  maxDrawdown: decimal("maxDrawdown", { precision: 10, scale: 4 }),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export const systemStatus = mysqlTable("systemStatus", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  isActive: boolean("isActive").default(false).notNull(),
  mode: mysqlEnum("mode", ["PAPER", "LIVE"]).default("PAPER").notNull(),
  lastHeartbeat: timestamp("lastHeartbeat").notNull(),
  ticksProcessed: bigint("ticksProcessed", { mode: "number" }).default(0).notNull(),
  signalsGenerated: int("signalsGenerated").default(0).notNull(),
  tradesExecuted: int("tradesExecuted").default(0).notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
});

export const aiInsights = mysqlTable("aiInsights", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("userId").notNull(),
  type: mysqlEnum("type", ["MARKET_ANALYSIS", "RISK_WARNING", "OPPORTUNITY", "PATTERN"]).notNull(),
  title: varchar("title", { length: 200 }).notNull(),
  content: text("content").notNull(),
  confidence: decimal("confidence", { precision: 5, scale: 4 }).notNull(),
  actionable: boolean("actionable").default(false).notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;
export type Trade = typeof trades.$inferSelect;
export type InsertTrade = typeof trades.$inferInsert;
export type Position = typeof positions.$inferSelect;
export type InsertPosition = typeof positions.$inferInsert;
export type Signal = typeof signals.$inferSelect;
export type InsertSignal = typeof signals.$inferInsert;
export type Performance = typeof performance.$inferSelect;
export type InsertPerformance = typeof performance.$inferInsert;
export type SystemStatus = typeof systemStatus.$inferSelect;
export type InsertSystemStatus = typeof systemStatus.$inferInsert;
export type AIInsight = typeof aiInsights.$inferSelect;
export type InsertAIInsight = typeof aiInsights.$inferInsert;
