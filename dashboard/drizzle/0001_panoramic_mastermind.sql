CREATE TABLE `aiInsights` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`type` enum('MARKET_ANALYSIS','RISK_WARNING','OPPORTUNITY','PATTERN') NOT NULL,
	`title` varchar(200) NOT NULL,
	`content` text NOT NULL,
	`confidence` decimal(5,4) NOT NULL,
	`actionable` boolean NOT NULL DEFAULT false,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `aiInsights_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `performance` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`timestamp` bigint NOT NULL,
	`equity` decimal(20,8) NOT NULL,
	`dailyPnl` decimal(20,8) NOT NULL,
	`dailyPnlPct` decimal(10,4) NOT NULL,
	`totalTrades` int NOT NULL,
	`winningTrades` int NOT NULL,
	`losingTrades` int NOT NULL,
	`winRate` decimal(5,4) NOT NULL,
	`profitFactor` decimal(10,4),
	`sharpeRatio` decimal(10,4),
	`maxDrawdown` decimal(10,4),
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `performance_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `positions` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`symbol` varchar(20) NOT NULL,
	`side` enum('LONG','SHORT') NOT NULL,
	`entryPrice` decimal(20,8) NOT NULL,
	`currentPrice` decimal(20,8) NOT NULL,
	`size` decimal(20,8) NOT NULL,
	`unrealizedPnl` decimal(20,8) NOT NULL,
	`unrealizedPnlPct` decimal(10,4) NOT NULL,
	`takeProfit` decimal(20,8),
	`stopLoss` decimal(20,8),
	`entryTime` timestamp NOT NULL,
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `positions_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `signals` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`symbol` varchar(20) NOT NULL,
	`side` enum('LONG','SHORT') NOT NULL,
	`confidence` decimal(5,4) NOT NULL,
	`price` decimal(20,8) NOT NULL,
	`reason` text,
	`status` enum('PENDING','EXECUTED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `signals_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `systemStatus` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`isActive` boolean NOT NULL DEFAULT false,
	`mode` enum('PAPER','LIVE') NOT NULL DEFAULT 'PAPER',
	`lastHeartbeat` timestamp NOT NULL,
	`ticksProcessed` bigint NOT NULL DEFAULT 0,
	`signalsGenerated` int NOT NULL DEFAULT 0,
	`tradesExecuted` int NOT NULL DEFAULT 0,
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `systemStatus_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
CREATE TABLE `trades` (
	`id` int AUTO_INCREMENT NOT NULL,
	`userId` int NOT NULL,
	`symbol` varchar(20) NOT NULL,
	`side` enum('LONG','SHORT') NOT NULL,
	`entryPrice` decimal(20,8) NOT NULL,
	`exitPrice` decimal(20,8),
	`size` decimal(20,8) NOT NULL,
	`pnl` decimal(20,8),
	`pnlPct` decimal(10,4),
	`fees` decimal(20,8) DEFAULT '0',
	`exitReason` varchar(50),
	`confidence` decimal(5,4),
	`status` enum('OPEN','CLOSED') NOT NULL DEFAULT 'OPEN',
	`entryTime` timestamp NOT NULL,
	`exitTime` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `trades_id` PRIMARY KEY(`id`)
);
