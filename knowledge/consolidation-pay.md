---
name: Consolidation Pay
key: consolidation-pay
aliases: Consolidation Pay, ConsolidationPay, Consolidation-Pay, ConPay, Consol Pay
description: Corporate platform for consolidated and bulk payment processing across multiple accounts and currencies.
---

# Consolidation Pay

## Overview
Consolidation Pay lets corporate treasury teams combine payments from many source accounts into a single
consolidated instruction, then disburse to multiple beneficiaries. It supports single payments, scheduled
runs, and CSV-driven bulk uploads.

## Business Flow
1. A corporate user signs in (SSO via **AuthGateway**) and selects a funding account.
2. The user creates a payment batch either manually or by uploading a CSV of payment records.
3. Each record is validated: mandatory fields, account/routing format, currency support, and duplicate detection.
4. Valid records move to an approval queue; invalid records are flagged inline for correction and re-upload.
5. An authorized approver reviews the batch (maker-checker) and submits it for processing.
6. Payments are routed to **PayGate** for execution; status updates stream back per record.
7. Every action — upload, edit, approve, submit, settle — is written to an immutable audit log.

## Key Use Cases
- Bulk upload of payment records via CSV with pre-submission validation and error highlighting.
- Maker-checker approval workflow with configurable approval thresholds by amount.
- Partial processing: valid records settle while invalid records are returned for correction.
- Audit and compliance reporting over all bulk-upload activity.
- Multi-currency consolidation with FX rates sourced from **FX Desk**.

## Design
- Batch is the core aggregate; each batch has many PaymentRecords with a per-record status machine
  (`uploaded → validated → approved → submitted → settled | failed | rejected`).
- Validation runs as a dedicated stage so a bad row never blocks a good row (row-level isolation).
- Idempotency keys on batch submission prevent duplicate disbursement on retries.
- Audit events are append-only and never mutated.

## Tech Stack
- Backend: Java 17, Spring Boot, PostgreSQL, Kafka (per-record status events).
- File handling: streaming CSV parser with schema validation; files staged in S3-compatible object storage.
- Frontend: React + TypeScript.
- Integrations: PayGate (execution), FX Desk (rates), AuthGateway (auth), LedgerCore (posting).
