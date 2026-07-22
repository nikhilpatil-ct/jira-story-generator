---
name: PayGate
key: paygate
aliases: PayGate, Pay Gate, Payment Gateway, Pay-Gate
description: Payment execution and routing gateway connecting internal apps to payment rails.
---

# PayGate

## Overview
PayGate is the execution layer that takes approved payment instructions and routes them to the correct
payment rail (ACH, SWIFT, SEPA, RTP), tracking each instruction to a terminal state.

## Business Flow
1. An upstream app (e.g. Consolidation Pay) submits an approved payment instruction with an idempotency key.
2. PayGate selects a rail based on currency, amount, geography, and cut-off times.
3. The instruction is enriched, screened for sanctions, and dispatched to the rail adapter.
4. Rail callbacks and polling update the instruction status; failures are classified as retryable or terminal.
5. Settlement confirmations are posted to **LedgerCore** and streamed back to the originating app.

## Key Use Cases
- Rail selection and least-cost routing.
- Sanctions/compliance screening before dispatch.
- Retry and reconciliation for in-flight and failed payments.
- Idempotent submission so duplicate requests never double-pay.

## Design
- Instruction state machine: `received → screened → dispatched → settled | returned | failed`.
- Rail adapters are pluggable behind a common interface.
- Outbox pattern guarantees status events are published exactly once.

## Tech Stack
- Backend: Go, gRPC, PostgreSQL, Kafka.
- Rail adapters: per-rail modules (ISO 20022 / NACHA formatting).
- Integrations: LedgerCore (settlement posting), sanctions screening service.
