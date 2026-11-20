# Meta Ads integration

## Configure and sync

An owner configures the Meta access token and selected ad account through `PUT /settings/integrations`. The token is business-scoped, omitted from settings responses, and accepted as a bearer token by the read-only Graph API client. The integration does not implement OAuth; supply a Meta token with the required `ads_read` permission using the existing secured settings flow.

Use these endpoints with an authenticated business context (`X-Business-ID`):

- `GET /meta-ads/status` — configuration and last successful sync state.
- `GET /meta-ads/accounts` — list accounts available to the configured token.
- `POST /meta-ads/sync/insights` — import a date range of at most 92 calendar days.
- `POST /meta-ads/sync` — sync the current date in Asia/Karachi.
- `POST /meta-ads/sync-history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — compatibility route for an explicit range.
- `GET /meta-ads/syncs/history` — inspect business-scoped run history.
- `GET /meta-ads/insights` — read imported account, campaign, ad set, or ad rows.
- `GET /meta-ads/overview`, `/campaigns`, `/adsets`, `/ads`, `/today`, `/analysis` — read reports from stored imports.

Sync routes require integration-management permission; read routes require analytics-read permission. The scheduled task uses the same sync service as manual requests. Switching a business to another ad account is blocked after a completed or partial import until a reviewed data reset is performed.

## Stored fields and definitions

Meta is queried at account, campaign, ad set, and ad levels with daily increments. The integration stores provider-reported spend, impressions, reach, clicks, link clicks, CTR, CPC, CPM, frequency, currency, action arrays, action-value arrays, cost-per-action arrays, and the requested attribution parameters. Numeric metrics are parsed as finite decimals or non-negative integers and rows with invalid identity/date data are skipped and counted. Repeated rows use the unique key `(business, account, level, entity, date_start, date_stop)` and update in place.

The request specifies `action_attribution_windows=["default"]` and `action_report_time="mixed"`; these values describe the request and are stored alongside the rows. The raw `actions`, `action_values`, and `cost_per_action_type` arrays remain available from `/meta-ads/insights`. Norfae's campaign `sales` field is a Meta-reported purchase action count when a recognized purchase action is present. It is not a verified Norfae order count. The integration does not add Meta action values to business revenue or calculate campaign ROAS. Purchase conversion values are retained for audit but are not exposed as verified profitability metrics.

For a multi-day campaign report, spend, impressions, clicks, and link clicks are summed. CTR, CPC, and CPM are calculated from those combined totals using clicks ÷ impressions × 100, spend ÷ clicks, and spend ÷ impressions × 1,000. Daily reach is not summed because people may appear on multiple days; period reach and frequency are therefore omitted when no unique period value is available. Account overview follows the same rule for reach.

Meta-reported purchase, lead, and messaging actions follow Meta's attribution/reporting behavior. They do not establish that a sale was delivered, paid, or attributed by Norfae. Business revenue and profitability remain separate deterministic Norfae calculations.

## Request and safety behavior

The client uses the configured Graph API version, HTTPS, bearer-token headers, disabled redirects, bounded connect/read timeouts, limited retries for transient/rate-limit failures, and validated provider pagination links. It strips any `access_token` query parameter from a paging link. It does not perform write operations. Provider error payloads and tokens are not returned to callers or included in sync summaries.

Each run is recorded as `running`, `completed`, `partially_completed`, or `failed`. Rows from successful levels are committed together with a partial status if another level or page failed. A wholly failed run does not retain insight changes. PostgreSQL row locking and an active run ID serialize syncs and account configuration changes for one business, including recovery from an expired run; a database uniqueness constraint protects state and insight identities.

The integration requires migration `20261122_0008` after the Shopify migration. The migration chain and offline Alembic metadata are inspectable without connecting to a database. Upgrade/downgrade/re-upgrade behavior still requires execution against the isolated PostgreSQL audit database; no such database operation is claimed as verified until local authentication is configured.

Meta API references: [Graph API overview](https://developers.facebook.com/docs/graph-api), [Marketing API](https://developers.facebook.com/docs/marketing-api/), [Insights endpoint](https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/), and [rate limiting](https://developers.facebook.com/docs/graph-api/overview/rate-limiting/).
