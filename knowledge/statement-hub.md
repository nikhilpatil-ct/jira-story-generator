---
name: StatementHub
key: statement-hub
aliases: StatementHub, Statement Hub, Statement-Hub, Statements, Reporting Hub
description: Statement generation, delivery, and self-service reporting for corporate clients.
---

# StatementHub

## Overview
StatementHub generates account statements and regulatory/operational reports, then delivers them through
CorpWeb, email, and API to corporate clients.

## Business Flow
1. On a schedule (or on demand), StatementHub pulls balances and journals from **LedgerCore**.
2. It renders statements per account in the requested format (PDF, CSV, MT940/CAMT).
3. Generated documents are archived and indexed for retrieval.
4. Clients download statements from **CorpWeb** or receive them via secure delivery channels.

## Key Use Cases
- Scheduled and on-demand statement generation.
- Multiple output formats (PDF, CSV, ISO 20022 CAMT, MT940).
- Self-service statement search and download in CorpWeb.
- Retention and retrieval for audit and compliance.

## Design
- Rendering is a queued job; large runs are sharded per account.
- Documents are content-addressed and stored in object storage with retention policies.
- Delivery adapters (portal, email, SFTP, API) are pluggable.

## Tech Stack
- Backend: Java 17, Spring Batch, PostgreSQL, object storage.
- Rendering: templating engine + PDF/format renderers.
- Integrations: LedgerCore (data source), CorpWeb (download surface).
