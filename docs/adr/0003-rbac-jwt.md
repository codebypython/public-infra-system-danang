# ADR 0003 — JWT + RBAC

**Status**: Accepted
**Date**: 2026-05-05

## Context

Need authentication usable from web app + future mobile + API integrations. Need authorization across 4 role-tiers, with the ability to expand toward fine-grained permissions later.

## Decision

- Bearer JWT with HS256, secret from env.
- **Access token**: 15 min TTL — small payload (sub, role, jti, iat, exp).
- **Refresh token**: 7 day TTL — recorded in `refresh_tokens` table; rotated on every use; hash-only stored (`SHA256(token)`); revocable.
- **RBAC**: `require_roles("admin", "operator")` dependency factory; checks `role` claim. Non-matching → 403.
- **Login throttling**: Redis counter `login:fail:<ip>:<email>` resets after 15 min; 5 fails locks out.

## Consequences

- ✅ Stateless auth; horizontal scale-out friendly.
- ✅ Refresh rotation defeats stolen-token replay (attacker would invalidate the legitimate user immediately on next refresh).
- ⚠️ JWT cannot be invalidated mid-flight — the 15-min access TTL bounds blast radius.
- 🔜 2FA TOTP for operator/admin scheduled for Sprint 3 — `users.totp_secret` field already in schema.
