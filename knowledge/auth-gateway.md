---
name: AuthGateway
key: auth-gateway
aliases: AuthGateway, Auth Gateway, Auth-Gateway, Authentication Gateway, IAM, SSO
description: Central authentication and authorization gateway (OAuth2/OIDC) for all platform apps.
---

# AuthGateway

## Overview
AuthGateway is the platform's identity provider and policy enforcement point. It issues and validates
tokens and answers authorization decisions for every downstream app.

## Business Flow
1. A user authenticates (password + MFA, or federated SSO) and receives an OIDC ID token plus an
   OAuth2 access token (JWT).
2. Downstream apps (CorpWeb, Consolidation Pay, etc.) send the access token on every API call.
3. AuthGateway validates the token signature, expiry, audience, and the requested permission scope.
4. Valid requests are allowed; invalid or under-scoped requests are rejected with **401/403**.
5. Tokens are refreshed via refresh tokens; revoked or expired sessions force re-authentication.

## Key Use Cases
- Single sign-on across all corporate apps.
- Token issuance, validation, refresh, and revocation.
- Fine-grained, scope-based authorization decisions.
- MFA enforcement and session management.

## Design
- Stateless JWT access tokens (short TTL) + rotating refresh tokens.
- Scopes/roles map to fine-grained permissions checked per endpoint.
- Common 401 causes: expired/invalid token, wrong audience, or missing permission scope.

## Tech Stack
- Backend: Java 17, Spring Authorization Server, PostgreSQL, Redis (session/token store).
- Standards: OAuth2, OIDC, JWT (RS256).
- Consumers: every platform app (CorpWeb, Consolidation Pay, PayGate, StatementHub, ...).
