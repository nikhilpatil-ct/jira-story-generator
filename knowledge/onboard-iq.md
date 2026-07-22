---
name: OnboardIQ
key: onboard-iq
aliases: OnboardIQ, Onboard IQ, OnboardKYC, Onboarding, KYC, Customer Onboarding
description: Customer onboarding and KYC/AML verification platform for corporate clients.
---

# OnboardIQ

## Overview
OnboardIQ handles the end-to-end onboarding of corporate clients: collecting entity details, verifying
identity documents, running KYC/AML checks, and provisioning access to the platform.

## Business Flow
1. A relationship manager or client starts an onboarding case and enters entity and beneficial-owner details.
2. Documents are uploaded and classified; data is extracted and validated.
3. KYC/AML screening runs (sanctions, PEP, adverse media); risk score is computed.
4. Cases above a risk threshold route to a compliance analyst for manual review.
5. On approval, the client entity and users are provisioned, and access is granted via **AuthGateway**.

## Key Use Cases
- Corporate entity and beneficial-owner data capture.
- Document upload, classification, and data extraction.
- KYC/AML screening with risk scoring and case management.
- Automated provisioning into CorpWeb once approved.

## Design
- Case-centric workflow with a state machine and SLA timers per stage.
- Screening providers are pluggable behind an adapter interface.
- Decisions and evidence are retained immutably for audit and regulator review.

## Tech Stack
- Backend: Python (FastAPI), PostgreSQL, Celery for async screening jobs.
- Document AI: OCR + ML extraction pipeline.
- Integrations: sanctions/PEP data providers, AuthGateway (provisioning).
