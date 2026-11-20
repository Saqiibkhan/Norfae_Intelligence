# Authentication and business access

## Configuration

Set `JWT_SECRET_KEY` to a randomly generated secret of at least 32 bytes. Keep it
out of source control and separate from `OPENROUTER_API_KEY`. `JWT_ALGORITHM`
currently supports `HS256`; `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 30.
Production configuration rejects missing, short, placeholder, or shared JWT
secrets. Development can start without a JWT secret, but registration and login
will return an authentication unavailable response until one is configured.

## Authentication endpoints

- `POST /auth/register` accepts `email`, `password`, and `business_name`, with
  optional `full_name`. It normalizes email, creates the user, business, and
  owner membership in one transaction, and returns a bearer access token.
- `POST /auth/login` accepts `email` and `password` and returns a bearer token,
  public user profile, and one active, internally consistent business
  membership when available. This business is informational; callers must
  still select the business on protected requests.
- `GET /auth/me` returns the authenticated user's public profile.

Send the token in `Authorization: Bearer <access_token>`. Passwords must be at
least 12 characters and no more than 72 UTF-8 bytes under bcrypt. Password hashes
are never included in API response schemas.

In Swagger at `/docs`, register or log in and copy the returned
`access_token`. Use **Authorize** and enter the token (Swagger's HTTP bearer
scheme adds the `Bearer` prefix). For business routes, provide the desired
`X-Business-ID`; `/businesses` lists all active businesses available to the
current user. The API validates this selection against active membership on
every request.

Example registration body (use a unique email and a private password):

```json
{
  "email": "person@example.com",
  "password": "replace-with-a-private-password",
  "full_name": "Example User",
  "business_name": "Example Business"
}
```

## Businesses and memberships

- `GET /businesses` lists the caller's active businesses.
- `POST /businesses` creates another business for the caller, with an owner
  membership.
- `GET` and `PATCH /businesses/{business_id}` require active membership.
- `GET /businesses/{business_id}/memberships` requires member-read permission.
- `POST /businesses/{business_id}/memberships` accepts an existing user's email
  and role (`admin`, `analyst`, or `viewer`). It does not accept an arbitrary
  user ID or create a user account.
- `PATCH` and `DELETE /businesses/{business_id}/memberships/{user_id}` require
  member-management permission. Owner membership cannot be demoted, disabled,
  or removed; ownership transfer is not implemented.

| Role | Business read | Business update | Analytics read | Member read/manage | Business settings | Integration credentials |
| --- | --- | --- | --- | --- | --- | --- |
| owner | Yes | Yes | Yes | Yes | Read/write | Manage |
| admin | Yes | Yes | Yes | Yes, except admins/owner | Read/write | No |
| analyst | Yes | No | Yes | No | No | No |
| viewer | Yes | No | Yes | No | No | No |

## Tenant selection and data boundary

Every business-data REST request must include `X-Business-ID` in addition to
the bearer token. The selected ID is checked against the caller's active
membership; clients cannot use another business's ID to select its records.
Tenant-aware sessions add business filters to ORM reads and refuse tenant-owned
access without a selected business context. System status requires
authentication.

The tenant schema migrations are `20261116_0003` and `20261116_0004` (current
head). The guarded backfill assigned the original 2 expense rows and 1 settings
row to development business ID 1. Revision `20261116_0004` enforces non-null
ownership on 12 business-owned tables; `audit_logs.business_id` remains
nullable for system-wide events. Integration credentials can only be replaced
or explicitly cleared by the owner. Responses expose connection status, never
token values.

The three legacy WebSocket endpoints remain closed because their broadcaster
does not yet provide business-specific channels. Background schedulers remain
off at application startup. If explicitly started, task entry points require
business IDs and use tenant context. Public `/`, `/health`, `/docs`, and
`/openapi.json` remain available.

## Development database provisioning

The development database has a dedicated owner and business created through
the normal registration API. The local verification script confirmed the
configured owner can log in and access business ID 1, and that a forged
business selection is rejected. Local development-only credentials are read
from ignored `.env` variables by the provisioning and verification scripts.
Never commit those values or print tokens and secrets. The provisioning script
refuses duplicate registration and does not bypass authentication. For a new
development database, set the documented variables locally and run the
provisioner once; do not use those credentials in production.

The migration and backfill preserve the existing business rows. Other tenant
tables were empty at provisioning time. For a separate database, first verify
the target environment and use the reviewed guarded preflight/backfill process;
do not assume this development business ID applies there.

## Local test command

From `backend` in PowerShell, run:

```powershell
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

The API tests replace the database dependency with an isolated in-memory SQLite
database and do not contact PostgreSQL, Shopify, Meta, or OpenRouter.
