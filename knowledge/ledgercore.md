---
name: LedgerCore
key: ledgercore
aliases: LedgerCore, Ledger Core, Ledger-Core, GL Core, General Ledger
description: Double-entry general ledger and accounting core for all financial postings.
---

# LedgerCore

## Overview
LedgerCore is the system of record for balances and financial postings. Every money movement in the
platform eventually results in a balanced double-entry posting here.

## Business Flow
1. Source apps (PayGate, Consolidation Pay, FX Desk) emit posting events for settled transactions.
2. LedgerCore validates that each posting is balanced (debits = credits) before committing.
3. Balances are updated per account; a running journal is maintained.
4. End-of-day processes produce trial balances and feed StatementHub.

## Key Use Cases
- Authoritative account balances and journals.
- Double-entry validation and reconciliation.
- Period-close and trial-balance generation.
- Source of truth for statements and regulatory reporting.

## Design
- Immutable journal entries; corrections are new reversing entries, never edits.
- Postings are grouped into balanced transactions that either fully commit or fully roll back.
- Event-sourced: current balances are a projection of the journal.

## Tech Stack
- Backend: Java 17, Spring Boot, PostgreSQL (partitioned journals), Kafka.
- Accounting: event-sourced ledger with CQRS read models.
- Integrations: PayGate, Consolidation Pay, FX Desk (inbound postings), StatementHub (outbound).
