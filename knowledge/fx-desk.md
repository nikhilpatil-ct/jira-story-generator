---
name: FX Desk
key: fx-desk
aliases: FX Desk, FXDesk, FX-Desk, Foreign Exchange Desk, FX
description: Foreign-exchange pricing and trade-execution service for cross-currency payments.
---

# FX Desk

## Overview
FX Desk provides live and forward FX rates and executes currency conversions that back cross-currency
payments across the platform.

## Business Flow
1. An app (e.g. Consolidation Pay) requests a rate for a currency pair and amount.
2. FX Desk returns a quote with a short validity window (rate lock).
3. If the caller accepts within the window, a conversion trade is booked.
4. The trade is confirmed, and the resulting posting is sent to **LedgerCore**.
5. Unaccepted quotes expire silently; expired quotes must be re-requested.

## Key Use Cases
- Real-time indicative and firm (locked) FX quotes.
- Rate lock with a validity window to protect against slippage.
- Trade booking and confirmation for accepted quotes.
- Rate feed for Consolidation Pay multi-currency batches.

## Design
- Quote objects carry a `valid_until` timestamp; execution past that fails and forces a re-quote.
- Pricing pulls from multiple liquidity providers with a configurable spread.
- Booked trades are immutable and reconciled end-of-day.

## Tech Stack
- Backend: Go, gRPC, Redis (hot quote cache), PostgreSQL (booked trades).
- Market data: streaming rate feeds from liquidity providers.
- Integrations: Consolidation Pay (rate consumer), LedgerCore (postings).
