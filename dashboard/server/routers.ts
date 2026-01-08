import { z } from "zod";
import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, protectedProcedure, router } from "./_core/trpc";
import * as db from "./db";

export const appRouter = router({
  system: systemRouter,
  
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return { success: true } as const;
    }),
  }),

  trading: router({
    // Get recent trades
    getTrades: protectedProcedure
      .input(z.object({ limit: z.number().optional().default(50) }))
      .query(async ({ ctx, input }) => {
        return db.getRecentTrades(ctx.user.id, input.limit);
      }),
    
    // Get open positions
    getPositions: protectedProcedure
      .query(async ({ ctx }) => {
        return db.getOpenPositions(ctx.user.id);
      }),
    
    // Get pending signals
    getSignals: protectedProcedure
      .query(async ({ ctx }) => {
        return db.getPendingSignals(ctx.user.id);
      }),
    
    // Get trade statistics
    getStats: protectedProcedure
      .input(z.object({ days: z.number().optional().default(30) }))
      .query(async ({ ctx, input }) => {
        return db.getTradeStats(ctx.user.id, input.days);
      }),
  }),

  performance: router({
    // Get performance data for charts
    getData: protectedProcedure
      .input(z.object({ days: z.number().optional().default(30) }))
      .query(async ({ ctx, input }) => {
        return db.getPerformanceData(ctx.user.id, input.days);
      }),
  }),

  hftSystem: router({
    // Get system status
    getStatus: protectedProcedure
      .query(async ({ ctx }) => {
        return db.getSystemStatus(ctx.user.id);
      }),
  }),

  ai: router({
    // Get AI insights
    getInsights: protectedProcedure
      .input(z.object({ limit: z.number().optional().default(10) }))
      .query(async ({ ctx, input }) => {
        return db.getAIInsights(ctx.user.id, input.limit);
      }),
  }),
});

export type AppRouter = typeof appRouter;
