---
name: CorpWeb
key: corpweb
aliases: CorpWeb, Corp Web, Corporate Web Portal, Corp-Web
description: Corporate banking web portal — the primary self-service UI for corporate clients.
---

# CorpWeb

## Overview
CorpWeb is the customer-facing corporate banking portal. It is the front door corporate users log into
to view accounts, initiate and cancel requests, manage users, and launch into downstream apps such as
Consolidation Pay and StatementHub.

## Business Flow
1. Corporate user authenticates through **AuthGateway** (OAuth2 / OIDC); CorpWeb receives a bearer token.
2. The portal shell loads entitlements and renders only the modules the user is authorized for.
3. User actions (initiate payment, cancel request, download statement) call backend APIs with the bearer token.
4. Each API validates the token and the user's fine-grained permissions before acting.
5. Long-running requests (e.g. cancellations) show status and can be retried.

## Key Use Cases
- Single sign-on entry point into all corporate banking modules.
- Initiate and **cancel** service requests (the Cancel API revokes an in-flight request).
- User and entitlement management for corporate administrators.
- Deep-links into Consolidation Pay, StatementHub, and FX Desk.

## Design
- Thin BFF (backend-for-frontend) aggregates downstream APIs and forwards the user's token.
- All privileged calls (including Cancel) require a valid, unexpired token plus the matching permission
  scope; a missing/expired token or missing scope yields **401 Unauthorized** by design.
- Token refresh is handled silently by the shell; a failed refresh forces re-authentication.

## Known Sensitive Areas
- The Cancel API is authorization-heavy: it checks token validity, API permission scope, and recent
  config changes. 401s here usually trace back to token validation or a permission/scope mismatch.

## Tech Stack
- Frontend: React + TypeScript, Vite, Redux Toolkit.
- BFF: Node.js (NestJS), talks to microservices over REST/gRPC.
- Auth: AuthGateway (OAuth2/OIDC, JWT bearer tokens).
- Observability: OpenTelemetry traces, centralized log aggregation.
