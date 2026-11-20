# Tenant data access and migration state

## Request boundary

All restored business-data REST routes require a valid bearer token and
`X-Business-ID`. The backend checks that the current user has an active
membership and that the business is active. Read requests require analytics
read; ordinary writes require business update; sync and integration writes
require integration management. Settings have their own role checks and return
no credential values.

`TenantSession` is used by application database sessions. ORM selects are
filtered by the active business; ORM writes receive the verified business ID
and reject mismatches. Tenant table access without a business context raises
`TenantContextRequired`. Order items carry a business ID and use composite
foreign keys to both their order and inventory product, so cross-business links
are rejected by the database.

Use a verified membership dependency to establish HTTP context. Background
entry points require explicit business IDs and use `tenant_scope`; application
startup intentionally does not start schedulers. The existing WebSocket
manager broadcasts globally, so all legacy WebSocket paths continue to close
before accepting connections.

## Applied migration and legacy data

`20261116_0003` added nullable business ownership to the 13 existing tenant data
tables, business-scoped unique constraints, indexes, and composite order-item
foreign keys. The guarded backfill assigned the audited 2 expenses and 1
settings row to the dedicated development business (ID 1), created through
`POST /auth/register`. No other tenant data rows existed during the preflight.

`20261116_0004` is the current revision. It enforces `NOT NULL` for the 12
business-owned tables. `audit_logs.business_id` remains nullable for
system-wide audit events. The migration preflights for unassigned rows before
altering any columns. The development-only registration and API verification
scripts read credentials from ignored local `.env` variables; never commit or
display those values.

## Validation

The tenant-isolation tests use an isolated in-memory SQLite database. They
prove cross-business read, update, and delete isolation for restored endpoints,
business-specific unique identifiers, settings separation, owner/role checks,
and rejection of cross-business order-item references. The development API
verification also checks selected-business endpoints and confirms that a
forged business selection is rejected.
