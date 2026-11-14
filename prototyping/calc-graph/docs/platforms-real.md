# Real construction-platform connections (Procore, Autodesk Build, Autodesk Forma)

Status 2026-11-14: built and contract-tested OFFLINE against synthetic recorded responses (45/45 checks).
**Never run against a real account yet** - that needs the credentials in section 9. Until then every
adapter falls back to the synthetic mock and says so on every record.

## 1. What is real, per platform

| Platform | Official machine-readable spec | Typed client | Read live | Write (seed) |
|---|---|---|---|---|
| Procore (REST v1.x) | Yes: full OAS 3.0, "download OAS" (63 MB, 2,305 paths) | Generated (openapi-python-client 0.29.1) - 22 operations | submittals, RFIs, change events, change order packages, commitments, schedule tasks, drawings, cost codes | RFIs, submittals, change events (sandbox only) |
| Autodesk Build / ACC (APS; renamed "Forma Build" on 2026-03-24) | Partial: aps-sdk-openapi has Authentication, Data Management, Issues, Account Admin only | Generated for DM + Issues + Account Admin; **hand-written** (`acc_rest.py`, cited per endpoint) for RFIs v3, Submittals v2, Cost, Sheets | submittals, RFIs, PCOs, OCOs, budgets, sheets, issues | RFIs, submittals (draft), PCOs (trial project, allowlisted) |
| Autodesk Forma (site/building design; API now called "Forma Site Design API") | None published | Plain cited calls (`forma_live.py`) | proposals + their element trees | none (read-only by design) |

**What Forma actually offers.** The Forma developer docs are marked "BETA ... intended for beta users only"
and every HTTP endpoint is `v1alpha`/`v2alpha`. There are two extension types: *embedded views* (a page
you host, loaded in an iframe inside Forma, using the `forma-embedded-view-sdk`) and *HTTP APIs* "to
interact with Forma from outside the application" with a 3-legged APS token (`data:read` / `data:write`).
The HTTP surface is elements/blobs, geometries, Integrate (write elements), library, proposals, sites,
sun analysis and terrain. There are **no RFIs, submittals, cost or schedule** in Forma: it is an
early-design tool, so it can only contribute proposals and the elements in them. The adapter reads
proposals and elements; a Forma element links to the registry only when its name is a registry id (or
carries a calc-graph marker). Unverified: an end-to-end server-side call (Autodesk's only worked auth
example is browser PKCE inside an extension), and whether the beta needs a sign-up.

Name collision to keep straight: since 2026-03-24 Autodesk uses "Forma" both for this design product and
for its AEC industry cloud that now contains ACC (Autodesk Build -> Forma Build, Autodesk Docs -> Forma
Data Management). Autodesk states "no changes to URLs, logins, APIs or integrations", so the ACC APIs
below are unchanged; that is why `aps-sdk-openapi` keeps the ACC Issues spec under a folder named `forma/`.

## 2. Files (all NEW; nothing the move-a-column builder owns was edited)

```
backend/calcgraph/platforms/live/
  __init__.py        SourcedAdapter: config selection, mock fallback, source labels; wrap_selected() hook
  secrets.py         data/secrets/ (gitignored, dir 0700, files 0600), env overrides, redact()
  oauth.py           authorization-code login, loopback callback on 127.0.0.1 (+ ::1), refresh, logout
  transport.py       generated-client calls, pagination, 429/503 backoff, redacted logging, Recorded transport
  links.py           calc-graph marker convention: platform record -> registry element ids
  procore_live.py    ProcoreLiveAdapter
  acc_rest.py        hand-written typed client: ACC RFIs v3, Submittals v2, Cost, Sheets (pydantic, extra=allow)
  acc_live.py        AccLiveAdapter (DM + Issues generated, the rest via acc_rest)
  forma_live.py      FormaLiveAdapter (read-only)
  generated/         procore_client, aps_issues_client, aps_dm_client, aps_admin_client (+ their subset specs)
  recorded/          synthetic recorded responses for the contract tests (spec-validated)
scripts/
  gen_platform_clients.py     regenerate the typed clients (pinned generator, pinned APS commit, Procore sha256)
  platform_auth.py            setup / login / status / projects / use / allow-seed / logout
  seed_platform_sandbox.py    seed a Procore sandbox / ACC trial project from the synthetic v2 model (dry run default)
  make_platform_recordings.py build the recorded responses
  check_platform_contracts.py the contract tests (no pytest; plain script, exit code)
```
Also edited: `.gitignore` (+ `data/secrets/`), `pyproject.toml` / `uv.lock` (+ `httpx`, `python-dateutil`, the
runtime of the generated clients).

## 3. Selection, fallback, labels

| Env | Effect |
|---|---|
| `CALCGRAPH_PLATFORM_PROCORE=live` | Procore live (`PROCORE_ENV=sandbox` default, or `monthly`; production refused) |
| `CALCGRAPH_PLATFORM_ACC=live` | Autodesk Build live |
| `CALCGRAPH_PLATFORM_FORMA=live` | Forma live |
| unset / anything else | synthetic mock (default: no network) |

When live is selected but cannot build (no app credentials, not signed in, ids not configured, HTTP
error), the mock is served and `fallback_reason` says why. Every record carries
`fields["source"]` (`live` / `mock`) and `fields["source_label"]`; `describe()` returns `synthetic`,
`source`, `selected`, `fallback_reason`. A live source exposes no synthetic `state`, so status.py and
change_order.py take their "live adapter" branches. Deep links on live records are the vendor **API**
resource URLs (plus Procore's own `link` field on RFIs): no web-UI URL pattern is documented in either
API reference, so none is guessed.

### Registration (DONE 2026-11-14)

1. `platforms/__init__.py` `get_adapters()` wraps every mock with `wrap_selected` (the one place adapters are
   built); `get_mock_adapters()` returns the bare mocks for code that builds its own `SourcedAdapter` (the
   contract checks). Contract check C6 pins it.
2. `GET /api/v2/platforms` reports `mock`, `source` (live | mock), `selected` and `fallback_reason`; the UI's
   live / mock badge (where MOCK used to be hard-coded) reads them.
   Refresh after a login: `move_api._adapters()` caches the adapters only while `adapters_fingerprint()`
   (env selection + the files in data/secrets/ when any platform is live) is unchanged, so a login made
   after the server started is picked up on the next call; `POST /api/v2/platforms/refresh` forces a rebuild.
   One record: `GET /api/v2/platforms/{name}/{record_type}/{id}`, or `GET /api/v2/platform-record?url=<link>`.
3. Optional, `base.py`: a `source` field on `NormalizedRecord` instead of `fields["source"]`, and a
   `COMMITMENTS` record type (Procore commitments are read into `ProcoreLiveAdapter.extras` today).
4. Unknown schedule float (DONE): every adapter's records pass `base.normalize_records()` (in
   `PlatformAdapter._records`), which types `total_float_days` as a number or None plus `float_known`; consumers
   read `NormalizedRecord.total_float`. status.py reports the least REPORTED float and says which activities
   report none; change_order.py assumes 0 float there (an upper bound on delay) and warns. Contract checks
   D3-D5 cover it; D6 fails on any direct `fields["total_float_days"]` read.

## 4. Generated typed clients

`scripts/gen_platform_clients.py`, generator **openapi-python-client==0.29.1** via `uvx` (same pin as
gen_platform_models.py). Each subset keeps only the operations called, with their parameters, request
bodies and 2xx responses; examples stripped; Procore `allOf`/`oneOf` serializer views flattened;
`filters[...]` / `sort[...]` list params and `custom_field_%{...}` template keys dropped.

| Package | Source | Pin |
|---|---|---|
| procore_client | https://developers.procore.com/api/v1/resource_groups/full_oas?version=1 | x-created-at 2026-11-13T21:00:38.939Z, sha256 `bb8e062a...ef4d` |
| aps_issues_client | aps-sdk-openapi `forma/issues/Issues.yaml` | commit `1e2490246ad3e05c86bc97ca20719054fce54a9e`, Apache-2.0 |
| aps_dm_client | aps-sdk-openapi `datamanagement/datamanagement.yaml` | same commit |
| aps_admin_client | aps-sdk-openapi `forma/accountadmin/accountadmin.yaml` | same commit |

Requests are built by each generated operation's own `_get_kwargs` (path, query, header names such as
`Procore-Company-Id` come from the spec); the generated `_parse_response` then runs as a contract check,
and a typed-parse failure is recorded in `session.parse_errors` with the operation name instead of
blanking the panel.

## 5. Endpoints covered

**Procore** (base `https://sandbox.procore.com` or `https://api-monthly.procore.com`; header `Procore-Company-Id`):

| Read | Write (seed) |
|---|---|
| GET /rest/v1.0/companies; GET /rest/v1.1/projects?company_id= | POST /rest/v1.0/projects/{project_id}/rfis |
| GET /rest/v1.1/projects/{project_id}/submittals | POST /rest/v1.1/projects/{project_id}/submittals |
| GET /rest/v1.0/projects/{project_id}/rfis | POST /rest/v1.1/change_events?project_id= |
| GET /rest/v1.1/change_events?project_id= | lookups: GET .../rfis/potential_rfi_managers, |
| GET /rest/v1.0/change_order_packages?project_id= | GET /rest/v1.0/specification_sections, |
| GET /rest/v1.0/commitments?project_id= | GET /rest/v1.0/companies/{company_id}/submittal_statuses, |
| GET /rest/v1.0/tasks?project_id= | GET /rest/v2.0/companies/{company_id}/change_events/statuses |
| GET /rest/v1.1/projects/{project_id}/drawing_areas; GET /rest/v1.1/drawing_areas/{id}/drawings | (+ GET /rest/v1.0/change_types, generated, unused) |
| GET /rest/v1.0/cost_codes?project_id= | |

Pagination `page` (1-based) + `per_page`, stop on a short page / no `rel="next"` in `Link`. 429/503:
wait `X-Rate-Limit-Reset` (unix s) or `Retry-After`, with jitter, max 4 retries.
Not served: budget lines (v1.x has no list-by-project GET); task total float (not in the task object).
Found while building: the v2.0 change-event status list returns `id` as a **string** while the v1.1
create body takes `status.id` as an **integer** (the seeder converts); the RFI question object has
`body` only (no plain-text variant) - the schema checker rejected the guess.

**Autodesk Build** (base `https://developer.api.autodesk.com`; ACC project id = DM id without `b.`):

| Read | Write (seed) |
|---|---|
| GET /project/v1/hubs, /hubs/{hub}/projects, /hubs/{hub}/projects/{project} (generated) | POST /construction/rfis/v3/projects/{id}/rfis (status, title) |
| POST /construction/rfis/v3/projects/{id}/search:rfis (limit<=200, offset) | POST /construction/submittals/v2/projects/{id}/items (typeId, specId, title, stateId=draft) |
| GET /construction/submittals/v2/projects/{id}/items (limit<=50), /specs, /item-types | POST /cost/v1/containers/{id}/change-orders/pco |
| GET /cost/v1/containers/{id}/change-orders/{pco,oco}, /budgets (containerId == project id) | |
| GET /construction/sheets/v1/projects/{id}/sheets?currentOnly=true (limit<=100) | |
| GET /construction/issues/v1/projects/{id}/issues (generated) | |

Not served: schedule (no public ACC schedule REST API found); cost codes (ride on budget lines).
ACC submittals can only be **created** as draft / sbc-1 / mgr-1; later states need workflow transitions,
so the seeder writes the target status into the description instead of faking it.

**Forma**: GET `https://developer.api.autodesk.com/forma/proposal/v1alpha/proposals?authcontext=pro_...`
(limit<=100, `nextUrl` paging) and GET `.../forma/element-service/v1alpha/elements/{urn}?authcontext=&recursive=true`
(302 followed); optional `X-Ads-Region`.

## 6. Auth

| | Procore | APS (ACC + Forma) |
|---|---|---|
| Authorize | `https://login-sandbox.procore.com/oauth/authorize` (Monthly: `login-sandbox-monthly`) | `https://developer.api.autodesk.com/authentication/v2/authorize` |
| Token | `{login host}/oauth/token` | `.../authentication/v2/token` |
| Client auth | client_id + client_secret in the form body | HTTP Basic header (never also in the body: APS returns 400) |
| PKCE | not documented, not sent | S256, sent |
| Access / refresh | 5,400 s; refresh token single-use, rotates (new one saved each refresh) | ~60 min (docs inconsistent: 60 min / 1800 / 3599); refresh 15 days |
| Scopes | none (user permissions) | `data:read data:write data:create account:read` |
| Callback | `http://localhost:8791/oauth/callback/procore` (or oob, see 9) | `http://localhost:8791/oauth/callback/aps` |

Port 8791 was picked because 8765 is the Windows-bridge tunnel (analysis/bhom_etabs.py). The listener binds
loopback only, serves one request on the exact path, checks `state` (forged state refused), never logs the
query string, and shuts down. Tokens: `data/secrets/<platform>_token.json`, 0600.

## 7. Linking real records back to registry elements

The seeder writes a marker, the adapters read it: `[calc-graph SUB-05-L2-S1]` or
`[calc-graph RFI-004 el=F-2B,P-2B]`. Procore: RFI `reference` + end of question body; submittal
`description`; change event `external_data.origin_id` + `description`. ACC: RFI `reference` (max 20 chars:
`CG:RFI-004`) + end of `question`; submittal `description`; PCO `externalId`/`externalSystem`; issue
`description`. Element ids come from `el=` when present, else from the synthetic state by ref. An unmarked
record stays real and unlinked (`element_ids=[]`) - never a guessed link.

## 8. Seeding script (`scripts/seed_platform_sandbox.py`)

Writes 7 RFIs, 16 submittal packages (one per frame line / level / sequence, statuses as far as the API
allows) and 4 change events (Procore change events with manual cost-estimate lines; ACC PCOs). Default is a
**dry run** (GETs only, to resolve ids; `--offline` sends nothing). A write needs all of: `--apply`; Procore
sandbox host (production refused at config time); the project id in `seed_allowed_project_ids` (added with
`platform_auth.py allow-seed`); and `--confirm-project "<exact name>"` matching the API. Idempotent: refs
already present are skipped. Every Procore body is round-tripped through the generated request model
before it is sent.

## 9. Accounts and credentials to create (account owner)

Never paste a secret into chat, a terminal command line, or a file in the repo. The `setup` command asks
for it with hidden input and writes `data/secrets/` (gitignored, 0600).

**Procore (free, Developer Sandbox):**
1. Sign up at https://developers.procore.com/ ("Sign Up"), verify the email. A Developer Sandbox company
   with seed data is provisioned automatically; set its password from the second email.
2. My Apps -> Create a New App (name e.g. "calc-graph prototype"). On the app, Create Version -> add
   component **Data Connector -> User Level Authentication**.
3. Credentials tab -> **Developer Sandbox** panel -> Redirect URI -> Edit -> `http://localhost:8791/oauth/callback/procore`.
   (Only bare `http://localhost` and `urn:ietf:wg:oauth:2.0:oob` are documented. If Procore rejects the
   port/path, register `urn:ietf:wg:oauth:2.0:oob` instead and put `"redirect_uri": "urn:ietf:wg:oauth:2.0:oob"`
   in `data/secrets/procore_app.json`; `login` then asks you to paste the code Procore shows.)
4. Copy the **Developer Sandbox** Client ID and Client Secret (not the Production ones), then run
   `uv run python scripts/platform_auth.py setup procore` and paste them at the prompts.
5. `uv run python scripts/platform_auth.py login procore` -> sign in with the SANDBOX login.
6. `... projects procore` -> pick a sandbox project -> `... use procore <company_id> <project_id>` ->
   `... allow-seed procore <project_id>`.
7. In the sandbox web app (https://sandbox.procore.com) on that project: Project Admin -> Tool Settings ->
   make **RFIs**, **Submittals** and **Change Events** (Financial Management) active. The signed-in user
   needs Admin on RFIs/Submittals (RFI manager and submittal `status_id` are admin-only fields).
8. `uv run python scripts/seed_platform_sandbox.py procore` (dry run), then
   `... --apply --confirm-project "<project name>"`, then run the app with `CALCGRAPH_PLATFORM_PROCORE=live`.

**Autodesk Build (ACC trial, 30 days):**
1. Start a trial at https://construction.autodesk.com/trial/autodesk-build/ (Forma Build; includes a sample
   project). You become hub admin of the trial account.
2. APS app: sign in at https://aps.autodesk.com -> My applications -> pick a developer hub -> Create
   application -> type **Traditional Web App** -> callback URL `http://localhost:8791/oauth/callback/aps` ->
   enable the Data Management / Autodesk Construction Cloud (Forma) APIs (and "Forma APIs" for Forma).
3. `uv run python scripts/platform_auth.py setup aps` -> paste Client ID and Client Secret.
4. In the trial hub: Hub Admin (Account Admin) -> **Custom Integrations** -> Add -> paste the APS **Client ID**
   (not the secret) -> name it. (Whether a trial hub may add a custom integration is NOT verified.)
5. Create a project, e.g. "calc-graph sandbox - Harbor View", with Build activated; in Submittals -> Specs add
   03 20 00, 03 30 00, 05 12 00, 05 31 00, 07 81 00 (the submittal create needs a specId and creating specs
   by API is not verified); make sure Cost Management is set up so PCOs can be created.
6. `... login aps` -> `... projects aps` -> `... use aps <hub_id> <project_id>` -> `... allow-seed aps <project_id>`.
7. `uv run python scripts/seed_platform_sandbox.py acc` (dry run), then `--apply --confirm-project "<name>"`,
   then `CALCGRAPH_PLATFORM_ACC=live`.

**Forma (optional, read-only):** a Forma licence or trial (https://www.autodesk.com/products/forma/overview),
a project (its id is the `pro_...` authcontext), the same APS app (with Forma API access), then
`... use aps <hub_id> <acc_project_id> <pro_id>` and `CALCGRAPH_PLATFORM_FORMA=live`. The API is beta; access
may need Autodesk's approval (not verified).

## 10. Contract tests

`uv run python scripts/check_platform_contracts.py` - 45/45 PASS (2026-11-14). Groups: A recorded Procore
bodies vs the OAS schemas (36 bodies; an invented field is rejected); B adapters on recordings (counts,
generated-model parse errors = none, `Procore-Company-Id` on every request, marker -> element links, an
unmarked record stays unlinked, status normalization 16/16, string amounts, sandbox-only links, ACC void
dropped, RFI search body, Forma authcontext); C selection/fallback/labels; D change-order estimate and
construction status on a live-sourced set; E seeder (dry run plans, both refusals, 27 typed POSTs with
markers, idempotent re-run, production refused, ACC dry run + apply, --offline+--apply rejected); F
secrets 0600/0700, redaction, gitignore, OAuth URL shape, real loopback callback with PKCE + Basic auth,
forged state refused, Procore sandbox host; G no secret/token in 325 log lines.

## 11. Not verified (needs the real accounts)

- Any response from a real Procore sandbox, ACC trial or Forma project (recordings are ours, spec-shaped).
- Procore: whether `http://localhost:8791/oauth/callback/procore` is accepted as a redirect URI (only bare
  localhost and oob are documented); the sandbox token URL stated verbatim (host documented, path inferred
  from the production endpoints); PKCE; refresh-token lifetime; numeric rate limits; which tools are active
  in a fresh sandbox project; whether a non-admin sandbox user can set `rfi_manager_id` / `status_id`.
- APS: whether a 30-day trial hub can add a Custom Integration; whether `http://localhost:<port>/...` vs
  `127.0.0.1` both register (the tutorial uses `http://localhost:8080/oauth/callback/`); the item-types path
  (named on the items-POST page, its own page not opened); creating spec sections by API; region headers
  outside Cost; refresh-token single use; 429 headers outside Cost.
- ACC field-level contract for RFIs/Submittals/Cost/Sheets responses: only fields named on the reference
  pages are declared; there is no machine-readable schema to check against.
- Forma: a server-side 3-legged call end to end; beta access gating; how proposals relate to a root element
  beyond `children`.
- The `/api/v2` UI showing live records: blocked on the registration edit (section 3).

## 12. Sources (read 2026-11-14)

Procore (pages read via `https://developers.procore.com/documentation/content/<slug>`; canonical URL shown):
- OAS: https://developers.procore.com/api/v1/resource_groups/full_oas?version=1
- https://developers.procore.com/documentation/oauth-auth-grant-flow
- https://developers.procore.com/documentation/oauth-endpoints
- https://developers.procore.com/documentation/oauth-keys
- https://developers.procore.com/documentation/oauth-choose-grant-type
- https://developers.procore.com/documentation/oauth-client-credentials
- https://developers.procore.com/documentation/development-environments
- https://developers.procore.com/documentation/new-account
- https://developers.procore.com/documentation/quick-start-guide
- https://developers.procore.com/documentation/building-apps-app-types
- https://developers.procore.com/documentation/rest-api-overview
- https://developers.procore.com/documentation/pagination
- https://developers.procore.com/documentation/rate-limiting
- https://developers.procore.com/documentation/api-usage-guidelines
- https://github.com/procore/Procore-Sample-Python (README, oauth_main.py)
- https://support.procore.com/products/online/user-guide/project-level/admin/tutorials/add-and-remove-project-tools
- https://support.procore.com/faq/can-i-enable-the-change-events-tool-on-my-project

Autodesk APS / ACC:
- https://github.com/autodesk-platform-services/aps-sdk-openapi (commit 1e2490246ad3e05c86bc97ca20719054fce54a9e)
- https://aps.autodesk.com/en/docs/oauth/v2/reference/http/authorize-GET/
- https://aps.autodesk.com/en/docs/oauth/v2/reference/http/gettoken-POST
- https://aps.autodesk.com/en/docs/oauth/v2/developers_guide/field-guide
- https://aps.autodesk.com/en/docs/oauth/v2/developers_guide/scopes/
- https://aps.autodesk.com/en/docs/oauth/v2/tutorials/get-3-legged-token-pkce
- https://aps.autodesk.com/en/docs/oauth/v2/developers_guide/App-types/traditionalweb
- https://aps.autodesk.com/en/docs/oauth/v2/tutorials/create-app/
- https://aps.autodesk.com/en/docs/acc/v1/tutorials/getting-started/
- https://aps.autodesk.com/blog/autodesk-build-rfi-v3-api-released
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/rfis-rfi-search-POST/
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/rfis-rfis-POST
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/rfis-rfis-id-GET
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-GET
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-items-POST
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/submittals-specs-GET
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-budgets-GET
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-GET
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/cost-change-orders-changeOrder-POST
- https://aps.autodesk.com/en/docs/acc/v1/overview/field-guide/cost-management
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/sheets-sheets-GET
- https://aps.autodesk.com/en/docs/acc/v1/reference/http/sheets-version-sets-GET
- https://construction.autodesk.com/trial/autodesk-build/
- https://aps.autodesk.com/blog/get-know-new-autodesk-forma-industry-cloud

Autodesk Forma:
- https://aps.autodesk.com/en/docs/forma/v1/overview/
- https://aps.autodesk.com/en/docs/forma/v1/overview/extension-types/
- https://aps.autodesk.com/en/docs/forma/v1/overview/getting-started
- https://aps.autodesk.com/en/docs/forma/v1/reference/http-reference
- https://aps.autodesk.com/en/docs/forma/v1/reference/http-reference/proposal-listproposals-GET
- https://aps.autodesk.com/en/docs/forma/v1/reference/http-reference/element-getelement-GET
- https://aps.autodesk.com/en/docs/forma/v1/working-with-forma/element-system/forma-element-specification
- https://aps.autodesk.com/en/docs/forma/v1/working-with-forma/using-http-apis
- https://aps.autodesk.com/en/docs/forma/v1/reference/http-specification
- https://www.autodesk.com/products/forma/overview
