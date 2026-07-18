# ADR-0002: Multi-tenancy isolation and request context

Status: Accepted

Date: 2026-07-14

## Context

The v2.0 roadmap requires tenant isolation, data permissions, quotas, and an
optional business extensions. The current application has global users and roles,
and business records are generally protected by ownership or RBAC only. Adding
`tenant_id` to every table without first defining identity and request context
would create inconsistent isolation rules and make data migration unsafe.

## Decision

The first v2.0 implementation uses a shared database and shared schema with the
following boundaries:

- `User` remains a global login identity. Email stays globally unique.
- `TenantMembership` links a user to one or more tenants. A membership can be
  active or inactive and one membership is selected as the login default.
- Access tokens carry the selected `tenant_id`. The matching server-side user
  session also stores that tenant so a token cannot be reused in another
  tenant context.
- Tenant-scoped endpoints resolve an active tenant and membership before any
  business query runs. Missing, disabled, or mismatched context is rejected.
- Tenant-owned tables carry a non-null `tenant_id` foreign key and every read,
  write, export, aggregate, and batch operation applies the same tenant filter.
- Cross-tenant object lookup returns 404 to avoid leaking identifier validity.
- Superusers do not implicitly bypass tenant filters. Future platform-wide
  operations must use explicit platform administration endpoints and audit
  that scope separately.
- Existing data is assigned to a deterministic default tenant during migration.
  Existing users receive active membership in that tenant.

`Items` is the first vertical POC. User and role administration remain global
until tenant-aware role assignment is implemented in the next phase. Tenant
switching is intentionally not exposed before role grants are tenant-scoped.

## Rationale

- Shared-schema isolation fits the current SQLModel and Alembic architecture
  and allows incremental migration without provisioning databases per tenant.
- Keeping identity global supports one account joining multiple tenants and
  avoids duplicating password, MFA, OIDC, and social identity state.
- Binding tenant context into both JWT and `UserSession` makes the active tenant
  explicit and independently revocable.
- Denying implicit superuser bypass keeps normal business endpoints safe and
  makes platform support access visible by design.

## Consequences

- Role codes, role assignments, departments, menus, dictionaries, settings,
  files, messages, logs, and caches must be tenantized in later migrations.
- Login currently selects the active default membership. A tenant switch API
  and UI can be added only after role assignments are tenant-aware.
- Database uniqueness constraints on tenant-owned data must progressively move
  from global uniqueness to `(tenant_id, value)` uniqueness.
- Background jobs, imports, exports, metrics labels, file paths, and cache keys
  must receive explicit tenant context before they become tenant-aware.

## Acceptance criteria

- A fresh database and an upgraded database both contain the default tenant and
  memberships for all existing users.
- New login tokens and user sessions contain the same tenant identifier.
- Items created in one tenant cannot be listed, exported, read, updated, or
  deleted from another tenant, including by a superuser using another tenant.
- Tests cover cross-tenant identifier probing and list isolation.
- No tenant-scoped query relies on frontend filtering or request-supplied IDs
  without membership validation.
