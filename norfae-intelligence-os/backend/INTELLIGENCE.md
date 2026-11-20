# Phase 3 intelligence modules

## Architecture and boundaries

The backend has a typed `BaseAgent`, `AgentContext`, explicit `AgentRegistry`,
tenant authorization, order-level profit calculations, analytics, and reporting.
The data analysis, product intelligence, and city intelligence agents are
registered in `app/agents/intelligence_registry.py`. All three use deterministic
Python services; none calls an LLM.

Every `/intelligence` endpoint requires a bearer token, a verified active
membership selected through `X-Business-ID`, and analytics-read permission.
Service queries also specify the verified `business_id`; `TenantSession` adds a
second ORM scope. Read operations do not write to the database. Existing
`/products/intelligence` and `/city-intelligence/` legacy routes remain
available with their previous response behavior. The new `/intelligence`
routes expose typed responses and do not change legacy analytics calculations.

The legacy product service grouped observed order items, used stored item profit,
and printed record data; the legacy city service used stored order profit and
zero-filled missing financials. Their outputs are retained for compatibility.
New intelligence endpoints use the explicit calculations and limitations below.

## Data analysis and quality

The read-only `DataAnalysisAgent` validates `Order` and catalog `Product` rows.
Its report includes inspected, valid, and invalid record counts; missing fields;
duplicate order IDs and normalized SKUs; invalid quantities and financial
values; unknown statuses; future or missing source dates; unmatched or
inconsistently formatted SKUs; unusual numeric values; warnings; corrections;
and a normalization preview.

Proposed trimming/casing changes are returned as preview data only. Validation,
normalization suggestions, and database updates are separate operations; the
agent never updates source records. Outlier warnings alone do not make a record
invalid. These checks cover orders and catalog products, not every table or
external import format.

## Profitability rules

Calculations use Python `Decimal` over recorded numeric inputs and round to
cents using half-up rounding.

- Recognized revenue is `Order.selling_price` summed for delivered orders.
- Gross revenue before discounts is unavailable because there is no original
  list-price field. Discounts and refunds are unavailable because the schema
  has no corresponding amount fields.
- COGS, packaging, and delivery sum their `Order` fields for delivered orders.
  Null values are unavailable; recorded zero is a known zero.
- Advertising uses categorized marketing/advertising `Expense` rows when
  present; otherwise it uses delivered-order `marketing_cost`. Meta daily spend
  is excluded because it may duplicate ledger spend.
- Other costs combine order `other_expense` with non-marketing ledger expenses
  only when the sources do not both have non-zero totals. If they do, overlap
  cannot be ruled out and combined other expense/net profit are unavailable.
- Observed order profit is recorded delivered-order revenue less known COGS,
  packaging, delivery, selected advertising, and other costs. It remains an
  estimate and `complete` is false because discounts/refunds cannot be
  reconciled.
- Returned and cancelled orders are excluded from recognized revenue. Refund,
  reverse-delivery, recovery, and incurred-cost details are missing, so their
  liabilities are not inferred.
- Item contribution is `OrderItem.total_price - OrderItem.total_cost` for
  delivered order items. It excludes allocated packaging, delivery, advertising,
  business expenses, discounts, and refunds.
- Profit margin is observed profit divided by recognized revenue, times 100; it
  is unavailable when revenue is zero or required inputs are missing.

Existing float columns have zero defaults. An old default zero may conceal a
cost that was never recorded; that uncertainty cannot be recovered. Results
are estimates, never certified complete realized profit.

## Product intelligence

The `ProductIntelligenceAgent` combines business catalog `Product` rows with
matched `OrderItem` rows. It includes catalog products with no sales. SKU is the
  primary match; normalized product name is a fallback only when the match is
  unique. Duplicate normalized SKUs/names are reported; unmatched or ambiguous
  item rows are counted in report warnings rather than silently attached.

- Total units sold: sum item quantities on delivered orders.
- Order count: distinct orders containing a matched item in any status.
- Delivered/cancelled/returned indicators: distinct matching order counts by
  recorded order status. Rates use those status counts divided by product order
  count.
- Revenue and product cost: delivered item `total_price` and `total_cost` sums.
- Product contribution: delivered item revenue minus delivered item cost,
  calculated through `DeterministicProfitabilityService.product_contribution`.
- Contribution margin: contribution divided by delivered item revenue, times
  100; unavailable at zero revenue.
- Average selling price: delivered item revenue divided by delivered units.
- Fully allocated business profit is unavailable. Contribution is never
  described as final net profit.

Best and lowest products are ranked by available contribution and include only
products with delivered orders. Revenue-change comparisons use the immediately
preceding equal-length period, and appear only when both periods have at least
three delivered orders and prior revenue is positive. A change of at least 50%
is flagged as unusual. Recommendations are rule-based: negative contribution
triggers a price/cost review; sufficiently sampled cancellation/return rates of
30% or more trigger a reason review; unusual changes trigger investigation; and
products without orders are explicitly described as lacking evidence.

## City intelligence

The `CityIntelligenceAgent` groups business-scoped `Order` rows by normalized
city and province. Missing cities are kept in a separate `Unknown` bucket with
a warning; they are not discarded.

- Total orders: all recorded statuses in the selected period.
- Total revenue: sum `selling_price` for delivered orders only.
- Average order value: delivered revenue divided by delivered order count.
- Recorded delivery costs: sum recorded delivery fields across all statuses;
  this does not assert that each amount was incurred or paid.
- Product contribution: delivered revenue minus recorded order COGS using the
  shared deterministic contribution calculation.
- Estimated order profit: sum of the shared deterministic order estimates for
  delivered orders. It excludes unallocated business expenses, and is not final
  city profit.
- Cancellation and return indicators use recorded statuses and divide by all
  city orders. Refund amounts remain unavailable.
- City-level business expenses are unavailable because no reliable city
  allocation exists. Delivery costs are one visible cost, not the only city
  expense.

Best/lowest cities are ranked by available delivered product contribution.
Revenue changes use the prior equal-length period and the same minimum sample
and 50% threshold as product comparisons. Recommendations refer only to
calculated contribution, recorded cost, status rates, and sufficiently sampled
changes.

## API

All routes require bearer authentication and `X-Business-ID`.

- `GET /intelligence/data-quality`
- `GET /intelligence/profitability?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /intelligence/profitability/products`
- `GET /intelligence/profitability/orders/{order_id}`
- `GET /intelligence/products?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page=1&page_size=25`
- `GET /intelligence/products/{product_id}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /intelligence/cities?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /intelligence/cities/{city_name}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

Date bounds are inclusive. Orders are assigned to periods using confirmed
date, then source date, then creation date. Product lists use page sizes from 1
to 100. City detail can return multiple matches when a city name occurs in
multiple provinces. A product or city outside the selected business returns
404. Responses use typed schemas rather than ORM objects.

## Marketing and ads intelligence

`MarketingOverviewAgent`, `MarketingCampaignAgent`, and
`MarketingTrendsAgent` use deterministic calculations and the existing
`MetaAdsService`. They require verified business scope and `analytics:read`.
This module is read-only; it does not pause campaigns or change budgets.

Account-level daily statistics come from `MetaDailyStats` and include spend,
impressions, reach, clicks, link clicks, leads, and Instagram messages. Stored
daily rows do not include purchase counts or conversion value. Campaign,
ad-set, and ad snapshots are fetched from Meta on demand through the existing
integration; this module does not persist them. Meta-reported purchase actions
are attribution-window-dependent actions, not independently verified orders.
The current integration does not expose conversion value, so ROAS and
campaign-attributed profitability remain unavailable. Leads and messages are
not treated as purchases.

Metrics use available counts and spend:

- CTR = clicks / impressions * 100.
- CPC = spend / clicks.
- CPM = spend / impressions * 1000.
- CPA = spend / Meta-reported purchase actions, when that field was returned
  and the count is positive.
- ROAS = attributed conversion value / spend; unavailable because the current
  source does not supply conversion value.

A missing input or zero denominator produces an unavailable (`null`) rate;
zero is not substituted for unknown data. Campaign reports distinguish a
reported zero purchase count from an omitted purchase action field. Reach is
summed across daily account rows and may count people more than once. Observed
business revenue and the shared deterministic business profit estimate are
shown separately and are never presented as Meta- or campaign-attributed.
Campaign spend is not added to profitability a second time. For overview
spend, `MetaDailyStats.spend` wins on dates that also have
`Expense(source="meta")`; Meta expense rows fill only dates without a daily
statistics row. Non-Meta marketing expenses are shown separately. The
profitability service retains its existing expense selection rules and may
omit Meta daily spend when it has not been recorded in the expense ledger; the
response warns about this limitation.

Campaign comparisons use the immediately preceding equal-length period when
both date bounds are provided. Conclusions require at least 10 units of spend
and 100 impressions. CPC peer comparisons additionally require 20 clicks. A
spend change of 50% or more and a CTR decline of 30% or more are flagged only
when both periods have sufficient data. Recommendations suggest
investigations based on calculated metrics and never make campaign changes.

Marketing endpoints (all require bearer authentication and `X-Business-ID`):

- `GET /intelligence/marketing/overview?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /intelligence/marketing/campaigns?level=campaign|adset|ad&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page=1&page_size=25`
- `GET /intelligence/marketing/campaigns/{campaign_id}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /intelligence/marketing/trends?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

Date bounds are inclusive. Trends use stored daily statistics only and do not
infer missing days or reconstruct history from current campaign snapshots.
Campaign endpoints call Meta only when the selected business has a configured
Meta account and access token; provider errors become generic warnings without
exposing credentials.

## Creative intelligence

The existing `Creative` table contains a local database ID, name, platform,
spend, revenue, ROAS, CTR, CPC, and record creation timestamp. It does not
contain a Meta creative ID, campaign/ad association, performance reporting
period, impressions, reach, clicks, conversions, frequency, conversion value,
or image/video path. Meta's existing ad insights contain ad-level reports, but
do not include creative IDs or asset metadata. The implementation therefore
does not label ad statistics as creative statistics or infer creative history.

`CreativeIntelligenceAgent` requires verified business scope and
`analytics:read`. It returns tenant-scoped legacy records and explicitly labels
their source. Non-zero stored values are shown as recorded values. Stored zero
values are marked ambiguous because database defaults make an actual zero
indistinguishable from an unreported metric. Ranking compares only non-zero
recorded ROAS values. Date filters apply to row creation time, not to a known
performance period. No visual traits are correlated with performance, and no
causal claims are made.

The separate `VisualCreativeAnalysisService` accepts local image bytes and
optionally uses Pillow when present (Pillow is not a required project
dependency). It limits inputs to 10 MiB and 40 megapixels and reports image
dimensions, aspect ratio, and dominant colors. It does not perform OCR,
product recognition, scene detection, or composition interpretation. Video
analysis is currently unsupported. Existing records contain no stored media
assets, so no public visual-analysis endpoint is exposed; the service reports
missing assets without fetching URLs or accessing private media. Failures are
returned as typed statuses without disclosing file paths or image contents.

Creative endpoints (bearer authentication and `X-Business-ID` required):

- `GET /intelligence/creatives?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&page=1&page_size=25`
- `GET /intelligence/creatives/{creative_id}`
- `GET /intelligence/creatives/comparison?creative_ids=12&creative_ids=15`

Comparison is limited to records visible to the selected business and reports
requested IDs that were not found in that tenant. There is no creative trend
endpoint because the database does not retain dated creative performance
history. Future creative-level attribution requires storing Meta creative and
ad associations, reporting dates, performance metrics, and safely managed
media references. Any later visual/performance relationship analysis must be
treated as exploratory correlation, not causation.

## Anomaly detection

`AnomalyDetectionAgent` exposes deterministic, read-only findings from
business-scoped orders, expenses, stored Meta daily statistics, product
contribution, and city comparisons. It is registered in the intelligence agent
registry, requires `analytics:read`, and uses the verified business context.
Financial calculations and anomaly comparisons are Python calculations; no LLM
is used. Findings are computed on demand and are not persisted. IDs are stable
for the same business, metric, period, and entity, but results may change when
source data changes.

The default comparison uses up to 28 prior calendar days and requires 7 prior
dated observations for time-series metrics. A measured change of at least 50%
is flagged; with at least 14 baseline points, a 3 standard deviation change
can also be flagged. Rate metrics use percentage-point comparisons. Product
and city contribution/revenue comparisons use the immediately preceding
equal-length period. These are configurable code thresholds, not learned
seasonal models.

Metrics include daily order count, delivered revenue and average order value,
delivery cost per delivered order, cancellation and return rates, recorded
non-marketing expenses, stored Meta spend/CTR/CPC/CPM, product contribution,
and city delivered revenue. Only dates with source rows are analyzed; absent
dates are not assumed to be zero. Insufficient history is reported. Recorded
zeros may be ambiguous because several source fields have zero defaults.
Revenue is based on delivered orders and recorded selling prices; refunds,
discounts, causal explanations, and missing source data cannot be inferred.
Meta ROAS and campaign-attributed conversion value remain unavailable.
Explanations and investigation suggestions are descriptive prompts, not
verified causes or automatic actions.

Anomaly endpoints require bearer authentication and `X-Business-ID`:

- `GET /intelligence/anomalies?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&category=sales&page=1&page_size=50`
- `GET /intelligence/anomalies/summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /intelligence/anomalies/{anomaly_id}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

Date bounds are inclusive; omitted bounds default to the last 30 days ending
today. Category and severity filters are optional. List page sizes are 1 to
100. Detail lookup is limited to findings in the selected business and period;
unknown or foreign-tenant IDs return 404. The summary applies the same filters
without pagination.

## AI Business Assistant

`BusinessAssistantAgent` is registered in the existing typed agent registry
and remains the API entry point. It delegates orchestration to a compiled
request-scoped LangGraph graph. The graph state contains the question, trusted
user/business IDs, the validated `AgentContext`, the request's database
session, bounded conversation history, validated intent and date bounds,
selected domains, per-domain results/status, evidence keys, safe errors, and
the final draft. No checkpointer is configured; requests do not share graph
state or persist checkpoints.

The graph validates trusted input, classifies intent, builds a fixed task plan,
routes tasks through a per-service `TaskAdapterRegistry`, validates/combines results, prepares
evidence, generates the answer, and checks evidence references before it is
returned. Supported categories are profitability, product performance, city
performance, marketing, creative performance, anomalies, overview,
recommendations, data quality, multi-domain analysis, and unsupported. A
missing date range defaults to the trailing 30 days. Multi-domain and overview
plans select only the relevant fixed service adapters. Profitability analysis
also retrieves the preceding equal-length period from the same deterministic
service.

Adapters reuse deterministic profitability, product, city, marketing,
creative, anomaly, and data-quality services. Marketing uses stored overview
and trend data only; live Meta campaign calls are not made. Domain tasks run
sequentially. Each adapter worker creates and owns its own tenant-scoped
SQLAlchemy session, then rolls it back on an exception and closes it in a
`finally` block. The request session is used for authenticated conversation
reads/writes and is rolled back after reading history before analysis workers
run. Existing conversations are reloaded with business and user scope before
the response is written.

The dependency-aware scheduler preserves the plan's topological order and
never runs tasks in parallel. Every dependency must be terminal before a task
runs. Failure or skip of a required dependency skips its dependent; failure or
skip of an optional dependency permits execution with the declared finding
reported unavailable. Successful dependencies expose only findings explicitly
listed by the dependent task. A domain failure is recorded by safe error code
and does not prevent unrelated selected domains from running. Successful
partial results retain `partial` execution status; all-tool failure returns an
explicit unavailable answer and `failed` status. Unsupported intent skips
analysis tools.

There is a bounded application-level retry loop for task adapter errors
classified `TRANSIENT_FAILURE`; the configured task retry count and exponential
backoff are capped by settings. Other task categories are not retried. The
OpenRouter client separately owns bounded provider retries. Request budgets
limit elapsed request time, task attempts, and logical LLM calls. The
LangGraph recursion limit is an additional graph guard, not a substitute for
those budgets.

The LLM receives a provider-only projection of approved result roots, safe tool
statuses, projected evidence, the current question, and bounded user-authored
conversation history. Classification does not receive business result facts or
prior assistant responses. Before drafting, `provider_data.py` allowlists known
fact roots and recursively removes business/tenant/user/record identifiers,
credentials, connection details, internal metadata, raw issue details, and
normalization previews. Finding IDs and metric names are replaced with opaque
request-local aliases; source-service names and evidence references are omitted.
The projection retains supported metric values, periods, units, definitions,
evidence status/classification, and limitations. After Pydantic parsing, aliases
are restored inside the backend and the original findings are still checked
against the request-local successful task results and evidence provenance.
Internal service results, authenticated `AgentContext`, and the public response
shape are not changed. The public `verified_facts` field continues to contain
the original authorized service results.

This boundary removes selected identifier fields and sensitive containers; it
is not full privacy or semantic redaction. Arbitrary identifier-like text
embedded inside otherwise allowed string values is not guaranteed to be found,
and necessary business metrics and labels remain provider-bound. The API still
returns original result details to the authenticated tenant caller.

The LLM cannot query the database or choose a tool outside the fixed domain
list. JSON output is Pydantic-validated. Internal `AssistantClaim` records identify bounded finding
IDs, domain, metric, period, type, value, and unit. The final factual answer is
rendered from those claims only after each finding is traced to a successful
task result with valid evidence provenance. Metric, domain, period, unit, and
value must match the finding exactly; numeric claim prose is never taken from
the LLM. Unsupported or malformed references are omitted and noted safely.
Internal recommendation intents use a fixed action allowlist and validated
finding IDs; deterministic text is rendered only when the action fits the
finding status. The public assistant response fields remain unchanged.

System-generated no-results and response-budget fallbacks are tagged by
internal graph state and preserved as such. The graph resets that state at
input validation; neither request data nor LLM output can set the trusted
fallback marker. These fixed fallback messages contain no analytics assertion
that bypasses evidence validation. LLM drafts, including drafts after partial
task failure, continue through structured claim validation. Accepted claims
are rendered deterministically; unsupported claims are omitted. Missing
metrics remain unavailable and are never converted to zero.

Assistant profitability trend findings carry an explicit `comparison` object
with current and previous start/end dates, both net-profit values, signed
absolute change, percentage change when defined, unit, direction, and the
comparison definition. The previous interval remains the immediately preceding
equal-length interval generated by the existing profitability task adapter;
both values come from the same deterministic profitability service. Percentage
change is `(current - previous) / abs(previous) * 100`, rounded using the
existing service's Decimal rounding helper. It is omitted when previous profit
is zero. Periods must be adjacent and equal in length, and unavailable values,
incompatible units, or incompatible sources do not produce a complete trend.
Claims must match the full internal comparison payload, including both date
ranges and every calculated value. The deterministic renderer displays both
ranges and values, the signed change, and the percentage when defined. It does
not display model-supplied causal explanations. Provider evidence uses opaque
finding/metric aliases and includes the comparison dates and values; internal
evidence-reference keys remain in backend state for provenance validation and
are excluded from the provider projection. When a comparison is incomplete,
the final answer says it cannot be calculated rather than presenting a partial
trend.

Unavailable and conflicting findings cannot support established claims.
Estimates are labeled as estimates. Conflicts continue through the deterministic
conflict policy, which preserves both sources and does not select or average a
value. Missing values remain unavailable rather than becoming zero. The LLM's
free-form answer, interpretation, and recommendation prose are not exposed as
final factual content. Provider failures and malformed structured output
return a generic 503; prompts, credentials, provider messages, and raw tool
exceptions are not returned.

This validates structured metric identity and exact reported values; it does
not perform general natural-language entailment. Claim text is therefore not
trusted or displayed. Comparison claims are limited to exact findings already
extracted by deterministic services, and recommendation actions are limited
to deterministic templates. New recommendation types require explicit
applicability rules before they can be exposed.

Each response includes an execution ID, overall graph status, executed node
names, selected tool statuses, and safe error codes. Logs include this
structured execution metadata and error types, but no prompts, conversation
content, tokens, or business values. The graph uses an immutable compiled
definition and request-local state; it does not use persistent checkpointing or
parallel database sessions.

The internal `app.schemas.coordination_schema` contracts define `CoordinationTask`,
`TaskResult`, `AgentFinding`, `CoordinationPlan`, and `SharedFindingsContext`.
Tasks use the fixed intelligence-domain allowlist and validate parameters against
existing agent input schemas where available. Plans reject duplicate task IDs,
unknown or self dependencies, missing dependency references, cycles, and more
than 14 tasks. Findings carry source/evidence metadata and an evidence status;
they do not assign invented confidence scores. The graph state carries a
request-local plan and typed task results, without storing tenant identity,
database sessions, credentials, or service objects in `SharedFindingsContext`.
`finding_extraction.py` derives bounded findings from typed deterministic
service outputs, preserving null/unavailable values, zero values, reporting
periods, service provenance, evidence keys, and source limitations. No LLM
calculates or creates findings.

The sequential scheduler validates declared dependencies, executes ready tasks
in plan order, prevents repeat execution, and records pending/running/succeeded/
failed/skipped task states. Required prerequisite failure skips dependents;
optional prerequisite failure allows execution with explicit unavailable
finding IDs. Adapters receive only findings named in that task's finding
requirements. A profitability investigation creates product, city, marketing,
and anomaly follow-ups only when the deterministic current/prior net-profit
comparison supports a decline. Otherwise the follow-ups are marked skipped.
Dependency-aware execution and findings handoff are implemented; execution
remains sequential. Evidence conflict classification and deterministic
response enforcement are implemented, as described below.

The adapter registry is a fixed domain-to-adapter mapping; it rejects unknown
domains and duplicate registrations and does not import or invoke model-named
functions. Each adapter validates its task parameters, obtains the database
session and trusted business ID from the authenticated `AgentContext`, calls an
existing deterministic service, and validates a typed output. Domain mappings:

- `profitability` → `DeterministicProfitabilityService.overall` for current and
  preceding periods, plus `DeterministicProfitabilityService.products`.
- `products` → `ProductIntelligenceService.analyze_business` (output key `products`).
- `cities` → `CityIntelligenceService.analyze_business` (output key `cities`).
- `marketing` → stored `MarketingIntelligenceService.overview` and `.trends`.
- `creatives` → `CreativeIntelligenceService.list_creatives` (output key `creatives`).
- `anomalies` → `AnomalyDetectionService.detect` once for report and summary.
- `data_quality` → `DataQualityService.analyze` (output key `data_quality`).

Output wrappers reuse existing Pydantic service schemas. Adapter failures use
safe categories (`INVALID_TASK`, `UNSUPPORTED_DOMAIN`, `PERMISSION_DENIED`,
`DATA_UNAVAILABLE`, `VALIDATION_ERROR`, `TRANSIENT_FAILURE`, `INTERNAL_ERROR`);
raw exception messages are not returned. The graph retains its established
domain-level error codes and partial-result behavior. Optional unavailable
findings are represented explicitly and are not replaced with invented values.

Conversations and messages are stored in tenant-scoped tables. Access requires
bearer authentication, a verified active membership selected with
`X-Business-ID`, and `analytics:read`. A conversation is additionally restricted
to its creating user within that business. History sent to the model is capped
at the latest 10 messages; input messages are capped at 2,000 characters and
conversation listing is paginated. Deletion requires `business:update` and is
limited to the creating user. Migration `20261116_0005` creates the persistence
tables. Existing calculated metrics, missing discounts/refunds, incomplete
source history, and limited creative/marketing attribution remain limitations.

Assistant endpoints require bearer authentication and `X-Business-ID`:

- `POST /assistant/chat` with `{ "message": "...", "conversation_id": 123 }` (`conversation_id` optional)
- `GET /assistant/conversations?page=1&page_size=20`
- `GET /assistant/conversations/{conversation_id}?page=1&page_size=50`
- `DELETE /assistant/conversations/{conversation_id}`

The assistant uses LangGraph for request-scoped orchestration and does not
modify business data.

### Assistant execution reliability (Phase 4.4)

The assistant applies request-local limits from settings: `ASSISTANT_TASK_TIMEOUT_SECONDS`
(20 seconds, capped at 120), `ASSISTANT_REQUEST_TIMEOUT_SECONDS` (120 seconds,
capped at 300), `ASSISTANT_MAX_TASK_ATTEMPTS` (16), `ASSISTANT_MAX_LLM_CALLS`
(2), and `ASSISTANT_TASK_MAX_RETRIES` (1, capped at 2). Backoff is exponential
from `ASSISTANT_RETRY_BASE_SECONDS` (0.1 seconds) and capped by
`ASSISTANT_RETRY_MAX_SECONDS` (0.5 seconds). These values are validated by
application settings. The existing plan is limited to the seven fixed domains.
The dependency scheduler is request-local and sequential; there is no parallel
task execution, durable job queue, or cross-request budget state.

Only adapter failures classified as `TRANSIENT_FAILURE` receive the bounded
task retry, and the adapters currently invoke read-only deterministic services.
Timeouts, permission failures, invalid parameters, missing data, validation
errors, and unexpected failures are not retried. OpenRouter retains ownership
of provider retries (`OPENROUTER_MAX_RETRIES`); assistant request accounting
counts logical model calls and does not add another provider retry loop.
Safe task categories include `INVALID_TASK`, `UNSUPPORTED_DOMAIN`,
`PERMISSION_DENIED`, `DATA_UNAVAILABLE`, `VALIDATION_ERROR`,
`TRANSIENT_FAILURE`, `TIMEOUT`, `BUDGET_EXCEEDED`, and `INTERNAL_ERROR`.

Task execution traces are held in the request-local budget and emitted through
structured logs. Each task trace contains execution/task IDs, approved domain,
UTC start/end, duration, attempts, final status, safe error code, and dependency
statuses. Request summaries contain duration, planned/succeeded/failed/skipped
counts, task attempts, and logical LLM calls. Prompts, provider responses,
business result values, credentials, and raw exception messages are excluded.
The public assistant response contract is unchanged.

A task timeout does not assume that cancellation stops a Python thread. Each
adapter worker owns a dedicated tenant-scoped SQLAlchemy session, which it
creates and closes in the worker thread. On timeout, the adapter waits for the
worker to exit and release its session before returning `TIMEOUT`; on request
cancellation, it likewise joins the worker before propagating cancellation.
No cross-thread database-driver cancellation is attempted. Therefore the
configured timeout bounds when timeout handling begins, but a non-interruptible
database operation or blocking Python work can still delay the response until
that worker exits. The assistant releases its history-read transaction before
starting the graph and reloads an existing conversation before writing the
response. This implementation is sequential and offers no hard process-level
deadline.
Dependency scheduling and retries remain best effort within those limits.

### Evidence provenance and conflict handling (Phase 4.5)

`AgentFinding` retains its prior `evidence_status` field and adds an explicit
`evidence_classification`: `OBSERVED` (directly recorded), `CALCULATED`
(deterministically derived), `INFERRED` (interpretation, never a directly
observed fact), or `UNAVAILABLE` (missing/insufficient input). It also carries
data availability, an optional unit and metric definition, reporting period,
source domain/service, evidence reference, and limitations. Existing finding
constructors remain compatible: classification and data availability default
from evidence status; deterministic extraction marks supported raw creative
metrics observed and calculation outputs calculated. Unavailable findings must
have a null value and unavailable status. No confidence scores are generated.

Before findings enter assistant drafting, `evidence_validation.py` checks that
each finding is associated with a successful task result from the same domain
and that its evidence reference is a key in that result. Invalid findings are
excluded from validated evidence and produce only safe internal validation
codes. LLM answer evidence IDs continue to be checked against actual result
keys. Findings, validation reports, and conflicts exist only in the current
graph invocation; tenant scope and service access remain in authenticated
`AgentContext` and are never accepted from model output.

The deterministic comparison considers only findings with the same metric
name. Different metric names (for example ROAS and net profit) are not treated
as conflicts. Same-name evidence is classified as `VALUE_MISMATCH` /
`UNRESOLVED` when compatible definitions and periods differ in value;
`PERIOD_MISMATCH` or `DEFINITION_MISMATCH` / `NOT_COMPARABLE` when the periods,
units, or stated definitions differ; and `SOURCE_UNAVAILABLE` or
`INSUFFICIENT_EVIDENCE` / `INSUFFICIENT_DATA` when a value is missing, estimated,
or inferred. The engine never selects a preferred source or averages values.
Original findings are retained. For any non-resolved conflict classification,
deterministic response enforcement replaces generated conflict prose with a
classification-consistent explanation and keeps the finding references. The
LLM receives the validated evidence and conflict report for additional context,
but cannot override those classifications. No automatic `RESOLVED` outcome is
currently produced: the available schemas do not encode enough reconciliation
rules to establish why different source values disagree.

Metric definitions are only explicit for selected extracted metrics; otherwise
the comparison relies on metric name and unit. The system cannot detect every
semantic definition mismatch (such as delivered-order revenue versus all-order
revenue) when the source schema does not provide definition metadata. Such
cases need domain-specific definitions before stronger conflict conclusions
can be made. Evidence is request/business scoped by construction; this backend
does not persist findings or perform cross-business reconciliation.

## Testing and manual verification

From `backend` in PowerShell:

```powershell
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Authenticate through `/docs`, retrieve an accessible business ID from
`/businesses`, then call the intelligence routes with the bearer token and
`X-Business-ID` header. Tests use isolated SQLite; they do not require the live
PostgreSQL database and make no Shopify, Meta, or OpenRouter requests. The
session cancellation tests use a blocking SQLite user-defined function to keep
database work active; they verify ownership and cleanup behavior, not
PostgreSQL-specific query interruption.
