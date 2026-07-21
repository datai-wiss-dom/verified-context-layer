# Verified Context Layer — Architecture & Evidence (through v0.3a)


**Date:** 18 July 2026
**Project:** agentic-2026-493108 (number 129682754245), region us-central1
**Target Data Product:** `ecommerce-customer-intelligence` (entry group `@dataplex`),
sits over BigQuery view `ecommerce_views.customers`, which selects from an
Iceberg-backed table in a separate project.


---
**Author:** Wissem Khlifi ·




**July 2026**


## THE ARCHITECTURE (locked this session)


**Principle: store only what KC lacks. Read everything else live from KC.**


KC already harvests and tracks the source. Duplicating that is what earns the
"why are you shadowing my catalog" challenge. So the layer stores exactly one
thing KC has no concept of — a **verification claim** — and reads all liveness
signals from KC at check time.


```
VERIFICATION CLAIM  (stored in a custom KC aspect — the only thing KC lacks)
  verified_against : the source the MEANING was checked against
  verified_at      : when the meaning was verified
  source_tier      : the verdict (derived by the validator, not hand-typed)


LIVENESS SIGNALS  (never stored — read live at validation time)
  source last-changed : KC  entrySource.updateTime   (KC owns; authoritative)
  source exists?      : does the KC entry resolve      (KC owns)
  current schema      : KC  schema aspect              (KC owns)
```


**The validator's logic (deterministic, no LLM, no agent):**
```
verified_at OLDER than source's entrySource.updateTime  → verification stale → unverified
verified_against no longer resolves                     → dead pointer       → unverified
verified_at older than N days (policy)                  → stale by age       → re-check
else                                                    → verified
```


### Why this is the right architecture (and answers the KC PM)


The PM challenge: *"KC already harvests the table, tracks its schema, and updates
`entrySource.updateTime` when it changes. Why store your own etag and compare it
yourself instead of using the catalog?"*


Answer: **we do use the catalog.** The layer does not store or shadow freshness.
It **consumes** KC's `entrySource.updateTime` as the "source changed" signal, and
adds the one thing KC has no field for: a verification claim with a timestamp.
The verdict is a **join** KC cannot express:


| Axis | Question | Who has it |
|---|---|---|
| Freshness | did the source change? | KC — today (`entrySource.updateTime`) |
| Approval | did someone sign off once? | KC — roadmap, ~late Q2 2026 |
| **Verification currency** | **is the sign-off still valid given the change?** | **nobody — this layer** |


Approval and freshness don't compose on their own: someone approves, the source
later changes, and nothing links the two. This layer is the join — it invalidates
the verification claim when KC's freshness signal outruns it. That is not a missing
*field*; it is a missing *relationship*, which is harder to replicate and survives
even after Google ships approval (approval without drift-invalidation is still
broken).


**Design decision — etag dropped.** Earlier design stored a hand-captured
BigQuery etag as the baseline. Rejected this session for two reasons: (1) it is a
value we write ourselves, not a KC-authoritative fact — self-referential;
(2) KC's own `entrySource.updateTime` is authoritative and behaves correctly
(see evidence). The "now" signal is now KC's, the "then" signal (`verified_at`)
is ours. Nothing self-referential remains.


---


## EVIDENCE (all round-trip verified, this session)


### v0.1 — aspect type created & attached (COMPLETE)
- Created `aspectTypes/verification` (4 fields), validated with `--validate-only` first.
- Attached to the real Data Product `ecommerce-customer-intelligence`.
- Values confirmed in KC UI: verified_against, verified_at, source_tier.


### v0.2 — enum expanded (COMPLETE)
- `source_tier` widened to `official_docs | verified | draft | unverified`.
- Additive enum widening + reindex accepted by KC after creation (small finding:
  aspect model is not frozen the way "can't delete a field" implied).


### v0.3a — baseline sealed (COMPLETE)
- Wrote `source_tier=verified`, `verified_at=2026-07-18T17:33:19Z`, plus the
  then-current source etag. UI-confirmed.


### Drift PROVEN (this session)
- Sealed against view etag `vVQOQhEqawtX5afd9Dt2Sg==`.
- Changed the view (`CREATE OR REPLACE`), etag moved to `Te/P+n0FkI0hoJ2vnmSJUA==`,
  restore moved it again to `dSKP2VQZX5NCrMIJDCiGZQ==`.
- Confirms the source's change is externally detectable.


### KC freshness signal characterized (this session — the key finding)
- The harvested `@bigquery` entry for `ecommerce_views.customers` carries just two
  aspects: `bigquery-view` and `schema`. **No verification field.** KC tracks the
  schema and the view; it does not track whether meaning was verified.
- `entrySource.updateTime = 2026-07-18T17:49:30.658Z` — moved when the view was
  edited today.
- **Stability test:** read 5× including two hand-checks ~1 hour apart. Value held
  at `17:49:30.658Z` every time with no source change. → `updateTime` reflects
  real source change, NOT re-scan. Honest label: "observed to move on change and
  stable across re-reads (n=5)"; not exhaustively proven to move on *every* change.


### Read path corrected (scar fixed this session)
- `--view=FULL` returns **keys only** for optional (non-required) aspects — this is
  documented behavior of `FULL`, NOT a KC bug. Confirmed via Google enum reference.
- `--view=CUSTOM --aspect-types=<type>` returns the aspect **data**. This is the
  correct read path for the validator to read a verification claim back from KC.
- Correction to prior scar: "view=FULL returns {}" was operator error on the view
  parameter, not a KC defect.


---


## GOVERNANCE-WORKFLOW CHECK (this session)


KC Governance Workflows (Preview) gate **consumer/agent access** to Data Products
via IAM (the target product's only action is "Request access for AI Agent Service
Accounts"). They do **not** gate content verification. Content-approval (metadata
change workflows) is a Google-stated roadmap item (~late Q2 2026), not active.
Confirmed in-project + docs. So: access-gating exists; content-verification does
not; this layer is the latter.


---


## HONEST SCOPE / LIMITATIONS


- **BigQuery assets only** for v0 (Data Products currently sit over BigQuery).
  Spanner/other = v1.
- **Baseline trust:** the verification claim is only as trustworthy as the seal.
  The seal must always be written by the validator reading the live source — never
  hand-typed. A hand-edited aspect could fool the drift check. Harden later;
  note now.
- **KC holds the claim, cannot protect it:** anyone with catalog-edit could alter
  the aspect. Acceptable for a reference implementation; state it.
- **`updateTime` characterized, not proven** to move on every possible change.
- Watch-outs remain **empty** until the validator runs and something breaks in
  practice.


---


## COMPETITIVE / ROADMAP POSITION


- KC is Preview; metadata-approval workflows are "~late Q2" roadmap. The window to
  be *ahead* of the product is weeks. Framing must be "reference architecture built
  on KC primitives, ahead of the product, on the product's own gap" — never
  "KC can't do this."
- The currency-join (freshness × verification) survives even after Google ships
  approval, because approval alone does not invalidate on drift.


---


## NEXT


- **v0.3b — the validator.** Plain Python, no LLM/agent. Reads verification claim
  via CUSTOM view; reads `entrySource.updateTime` live; compares `verified_at`
  vs `updateTime`; dead-pointer + staleness; writes `source_tier` verdict back.
  First real run flips the current claim to `unverified` (source changed after
  verified_at) — that flip IS the demo.
- **v0.4 — wrapper MCP** returning only entries that pass.
- **v2 — two ADK agents**, same catalog, raw MCP vs wrapper: one grounds on
  unverified context and answers wrong, one cannot.
- **v1 — Spanner seam** (DM), where the validator meets the write-never-persist scar.


---


## v0.3b COMPLETE — validator working, drift-invalidation proven live (18 Jul 2026)


**Design correction this session (David's catch):** the drift signal is the
**source etag**, NOT `entrySource.updateTime`. Reason: the steward certifies a
specific *version*; the etag *is* that version's fingerprint. `updateTime` only
says *when* something changed, not *what* it changed to. Etag confirmed stable
across re-reads with no change (true version fingerprint) and confirmed to move
on change. So: **etag = primary verdict (certified version vs current version);
updateTime = reported context ("when it last changed").**


**`vcl.py` — check + enforce modes, deterministic, no LLM, no agent.**
Shells to `gcloud`/`bq` (proven auth path). Reads the verification claim via
CUSTOM view (FULL returns keys-only — documented, not a bug). Reads live source
etag via `bq show`. Compares. `enforce` writes the verdict back, touching ONLY
the verification key (no collision with the live operational-health PATCher).


**Proven live run (enforce), against the drifted state:**
```
claim.source_etag  : vVQOQhEqawtX5afd9Dt2Sg==   (version the steward certified)
source.etag (live) : dSKP2VQZX5NCrMIJDCiGZQ==   (current version)
VERDICT: UNVERIFIED  (DRIFT - current version != certified version)
ENFORCE: writing source_tier 'verified' -> 'unverified' ...
```
**UI confirmed: Source Tier now shows `unverified`** (was `verified`). The flip
happened with no human and no LLM — a deterministic version comparison demoted
the trust state of a real Data Product in Knowledge Catalog.


**The full loop, demonstrated end to end:**
certify a version -> source drifts -> machine detects -> trust demoted, automatically.
This is the thing KC's roadmap approval-workflow cannot do: approval is a one-time
human event; this invalidates the certification when the source outruns it.


**v0.3c (David's idea, next — upgrades the model):** certification should cover the
whole trust surface, not just technical version. Multiple anchors, one per
dimension — technical (etag, have now), **data quality (DQ scan pass/fail, next)**,
semantic (glossary term version). Verdict = verified only if ALL anchors still
match, and it can say WHICH one drifted. Make the claim structure a LIST of
{dimension, verified_against, fingerprint}, not fixed fields, so dimensions are
data not code. Build DQ next IF scans exist on the source (unverified — check
first). This upgrades the project from "schema drift detection" (common) to
"trust-surface drift" (nobody does this).


**Still ahead:** seal mode (re-certify: capture current etag, write fresh claim);
deploy validator as scheduled Cloud Run job (v0.3c infra); wrapper MCP as Cloud
Run service (v0.4); two-agent demo (v2); Spanner seam (v1).


---


## v0.3c FOUNDATION — multi-asset architecture decided & schema committed (19 Jul 2026)


**Problem (David's catch):** a Data Product can have multiple assets. One flat
`source_etag` field cannot represent N assets, each checkable on M dimensions
(technical/quality/semantic). The single-fingerprint model breaks the moment a
Data Product has more than one table — the normal case.


**Round-trip read that decided the design:** the Data Product's own
`data-product` aspect DECLARES its assets, cleanly and parseably:
```json
"assets": [
  { "name": "//bigquery.googleapis.com/projects/.../datasets/ecommerce_views/tables/customers",
    "type": "bigquery.googleapis.com/Table" }
]
```
This is the manifest. The validator does NOT need assets passed by hand or a
separate discovery call — it reads the Data Product, gets `assets`, and walks
them. This is the auto-discovery/automation answer AND the multi-asset answer at
once: input is just the Data Product; sources are discovered from its own aspect.


**Two KC constraints found (both via validate-only, both worth telling a customer):**
1. **Aspect schemas are append-only.** Removing a field →
   `400 Backwards incompatible template changes are not supported`. You may add
   fields, never delete. (First test tried to replace the flat fields; rejected.)
2. **Nested record arrays ARE supported.** An `array` field whose `arrayItems` is
   a `record` validates cleanly. Confirmed by the additive test.


**Schema committed (v3, additive):** kept all four legacy flat fields (append-only
rule), ADDED `anchors` as `array<record{asset, dimension, fingerprint}>`. Field
list confirmed by round-trip describe:
`['verified_against','verified_at','source_tier','source_etag','anchors']`.


**Architecture chosen — Option A (anchors list in one aspect on the Data Product):**
```
seal   : walk Data Product's assets[]; for each asset+dimension, capture the
         current fingerprint; write the anchors[] list into the aspect.
check  : read anchors[]; for each, re-read current fingerprint, compare;
         verdict = AND across all anchors; name WHICH asset/dimension drifted.
enforce: check + write rolled-up source_tier back.
```
Legacy flat fields remain (append-only) but go unused by the v3 validator.


**Fingerprint strategy is per-dimension (not one etag for everything):**
- technical → BigQuery view/table etag (proven working in v0.3b)
- quality   → DQ scan pass/fail + job id. NOTE: DQ scans run on TABLES not VIEWS
  (verified: "a data quality scan runs on only one BigQuery table"). The Data
  Product certifies the view; the quality anchor points at the BASE table. Two
  anchors, two resources, same trust surface — correct, not a workaround.
- semantic  → glossary term version (later; needs glossary-link + term-etag check)
- lineage   → DEFERRED. Candidate justification only: base-table swap under
  Iceberg federation that doesn't move the view etag. Test that it escapes the
  etag before building; otherwise redundant with technical.


**NEXT SESSION (the refactor — substantial, do fresh):**
- Refactor `vcl.py` `seal`/`evaluate` to loop over the Data Product's assets[]
  and read/write the `anchors[]` list instead of the single hardcoded source.
- Verdict rollup + per-anchor drift naming.
- Then: quality anchor (DQ scan on base table) — round-trip the scan result
  format first (does it expose stable pass/fail + job id?).
- Anchors toggleable (--check-technical/--check-quality/--check-semantic),
  default technical only.


**Status:** thesis proven (v0.3b, live). Multi-asset architecture decided and
schema committed (v0.3c foundation). The refactor itself is not yet built —
that's the next focused session. L7 claim still rests on v2 (two-agent visible
proof) and the multi-dimension trust-surface story, neither built yet.


---


## v0.3c COMPLETE — multi-asset validator working, auto-discovery proven (19 Jul 2026, ~17:20)


**Probe first (de-risk):** wrote one hand-built anchor to the aspect, read it back
via CUSTOM view. `anchors present: True, count: 1`, full record intact. Nested
record arrays round-trip in KC — NOT the write-accept-never-persist scar; arrays
behave correctly. Green light before the refactor.


**Refactored `vcl.py` (v0.3c):** seal / check / enforce, deterministic, no LLM.
- **Auto-discovery:** reads the Data Product's own `data-product.assets[]` manifest
  and walks it. NO `--source-table` flag — the source is discovered from the Data
  Product itself. This is the automation/scalability answer.
- **Asset-name translator** (`asset_to_bq_ref`): parses
  `//bigquery.googleapis.com/projects/P/datasets/D/tables/T` -> `P:D.T` for bq show.
  Unit-tested: real asset resolves; Spanner/garbage/dataset-only return None (skip,
  no crash).
- **Per-anchor verdict:** verdict = AND across all anchors; drift attributed to the
  specific asset+dimension, not a bare "unverified".
- Scope: technical dimension only (fingerprint = BQ etag). quality/semantic later;
  the structure already holds them.
- Old single-asset version backed up as `vcl_v0.3b_singleasset.py`.


**Proven live, full sequence:**
```
seal   -> found 1 asset, technical = dSKP2VQZX5NCrMIJDCiGZQ==, wrote 1 anchor, verified
check  -> ok customers [technical] : matches -> VERIFIED
(change the view)
check  -> ! customers [technical] : DRIFT (dSKP... -> UShI50EOzG6ODvWSmsJBKg==)
          VERDICT: UNVERIFIED (1 of 1 anchor(s) drifted)
```
'1 of 1' becomes 'N of M' automatically when a Data Product has more assets — the
structure is genuinely multi-asset, demonstrated at N=1.


**Still ahead (unchanged):** seal not yet wired to Cloud Run schedule; quality
anchor (DQ scan on base table — round-trip the scan result format first); wrapper
MCP (v0.4); two-agent visible proof (v2); Spanner seam (v1); graph-discovery
control plane (north star — verify KC lineage hops first).


---


## v0.3c QUALITY ANCHOR COMPLETE — multi-dimension trust surface (19 Jul 2026, ~17:00)


**Second dimension added: data quality, staleness-aware.** The trust surface is now
technical (version) AND quality (freshness + pass/fail), checked independently per
asset, rolled up to one verdict, with per-anchor drift naming.


**Round-trips that shaped the design (read before build):**
- DQ scans run on TABLES not views (confirmed). The scan `customers--quality` runs
  on the base Iceberg table; the Data Product certifies the view. Two resources,
  same trust surface - correct.
- Scan exposes: `dataQualityResult.passed` (bool) + `executionStatus.latestJobEndTime`.
  Enough for a quality fingerprint.
- Scan does NOT record what data snapshot it ran against (no snapshot/version/
  watermark in the JSON). And the base Iceberg table is NOT reachable via plain
  `bq show` ("Dataset not found"). So change-based staleness (did the base data
  change since the scan) is NOT buildable via plain gcloud/bq - would need the
  Iceberg catalog snapshot read (alpha CLI / REST), deferred.


**Design decisions:**
- **Quality fingerprint = `PASS@<latestJobEndTime>`** (or FAIL@). Drift if the
  scan is now failing OR the passing result is older than the SLA.
- **Staleness is AGE-based, not change-based** (honest limitation): drift if
  `now - latestJobEndTime > freshness_sla_hours`. Catches "scan stopped running /
  nobody re-scanned". Does NOT catch "base data changed but scan hasn't re-run yet"
    - that needs the Iceberg snapshot read, noted as the upgrade.
- **Freshness SLA is stored in the anchor, set at seal, per the self-describing-claim
  principle** - not a check-time flag. Schema v4 added `freshness_sla_hours` (int)
  to the anchor record (additive, validated first). Policy travels with the
  certification; check is pure mechanism.
- **DP->scan mapping is explicit at seal (`--quality-scan ASSET=SCAN:HOURS`), not
  auto-discovered.** Auto-discovery of "which scan covers this asset" is the graph/
  control-plane job (north star), deferred. At N=1 the human declares the link,
  which is the correct certification act anyway.


**BUG caught by the live run (worth recording - the method working on our own code):**
`elif sla and age is not None and age > sla:` - Python treats `sla==0` as falsy, so
a 0-hour SLA (strict) silently DISABLED the staleness check. First live run with
SLA=0 wrongly reported "fresh". Fix: test `age is not None`, never truthiness; 0 is
a VALID strict threshold, not "no SLA". Had we trusted the predicted output instead
of the real run, this would have failed live in front of an audience. Round-trip on
the code's behavior, not just the API, caught it.


**Proven live, full sequence (after fix):**
```
seal (sla 24) -> technical customers = UShI...  ;  quality customers = PASS@12:47 (sla 24h)
                 wrote 2 anchors, verified
check (24h)   -> ok technical : matches
                 ok quality   : passing, fresh (4.0h ago, SLA 24h)
                 VERIFIED (all anchors match)
check (0h)    -> ok technical : matches
                 ! quality    : STALE (last run 4.1h ago > SLA 0h)
                 UNVERIFIED (1 of 2 anchors drifted)   <- staleness fires, technical stays green
```


**What this proves:** two independent trust dimensions on one asset; quality drift
on STALENESS (passing but too old) distinct from quality FAILURE (rules failing);
per-anchor attribution (names technical vs quality); roll-up verdict. This is the
"green dashboard, stale data underneath" case most tools miss.


**UI readability wart (noted):** technical anchors store `freshness_sla_hours: 0`
(by design - N/A for etag), which reads as "0-hour SLA" in the UI. Ambiguity between
"0 = strict" and "0 = N/A" is the same trap as the code bug. Cleaner: store null/
absent for dimensions that don't use it. Not urgent.


**Files:** `vcl.py` (current, technical+quality); `vcl_v0.3c_technical_only.py`,
`vcl_v0.3b_singleasset.py` (backups). Schema: `verification_v4_sla.json`.


**Still ahead:** change-based quality staleness (Iceberg snapshot read); semantic
anchor (glossary); seal->Cloud Run schedule; wrapper MCP (v0.4); two-agent proof
(v2); Spanner seam (v1); graph discovery (north star).


---


## Polish — technical anchors carry no freshness SLA (19 Jul 2026)


Absent-test (hand-built payload, technical anchor omitting freshness_sla_hours,
write + CUSTOM read-back): KC PRESERVES the omission — anchor returned with 3 keys,
`has sla field?: False`. Small finding: KC does not force-populate optional
array-record fields.


Design fix: `seal` now writes freshness_sla_hours ONLY on quality anchors. Technical
anchors omit it entirely (age is irrelevant to an exact etag match). This removes the
"0 = strict vs 0 = N/A" ambiguity that caused the falsy-zero bug — absent-means-N/A
cannot be misread. Confirmed live:
```
technical -> ['asset','dimension','fingerprint']
quality   -> ['asset','dimension','fingerprint','freshness_sla_hours']
```


Clarified three distinct clocks (do not conflate):
- **Scheduler cadence** — how often the validator runs. Operational; lives in the
  Cloud Run job config; one setting for the whole job.
- **Freshness SLA** — how old a certified result may be. Policy; per-anchor;
  QUALITY ONLY (a DQ pass has a shelf life; an etag match does not).
- **verified_at** — when the validator last confirmed the claim. Claim-level;
  auto-refreshed each scheduler run; answers "how recently did we check" for all
  dimensions at once.
  Technical needs no SLA: the scheduler drives verified_at, not a per-anchor SLA.


---


## measured_against — claim records what was actually checked (19 Jul 2026)


**David's catch:** the quality anchor's `asset` is the VIEW (from the DP manifest),
but the DQ scan runs on the BASE Iceberg table. The anchor was labeled with the view
while its fingerprint came from a different resource. Defensible (view sits on the
base table) but imprecise — an auditor couldn't see the fingerprint's real subject.


**Fix (schema v5, additive):** added `measured_against` to the anchor record.
Every anchor now records the actual resource its fingerprint was read from:
- technical -> the view (bigquery.../ecommerce_views/tables/customers) — reads the view's etag
- quality   -> the base table (biglake.../iceberg/.../namespaces/ecommerce/tables/customers) — where the scan runs


Chose "always populate" (option A) over "populate only when it differs" — explicit
beats implicit, per the falsy-zero / 0-vs-N/A lessons. Absent-means-something is a
trap; every anchor states its measured resource outright.


**Confirmed live:**
```
technical -> measured against: bigquery
quality   -> measured against: biglake/iceberg
```
Note: short names of BOTH resources are "customers" (view and base table share the
name) — only the full path distinguishes them. measured_against stores the full
path, so the claim is unambiguous even though display names collide. This is exactly
the kind of thing that would silently mislead an auditor reading short names.


`measured_against` is recorded, not compared — transparency, not a drift signal.
The check logic is unchanged.


---


## v0.4 FOUNDATION — lookup_context probed, wrapper design decided (19 Jul 2026, eve)


**Wrap target confirmed: `lookup_context`** — the grounding tool. Its description:
"Retrieves rich metadata regarding one or more data assets along with their
relationships." Output field is literally the LLM grounding context.


**Live-server findings (all corrected the docs — read the live call, not the doc):**


1. **Arg shape: `projectId` + `location`, NOT `name`.** The doc's Input Schema shows
   a single `name` field; the LIVE server rejects that ("invalid argument") and
   requires `projectId` + `location` as separate args, plus `resources[]`. Doc is
   stale on this. (A pasted LLM suggestion happened to get this right, but for the
   wrong reasons — the authoritative source is the live tool call, not the doc and
   not the suggestion.)


2. **Auth: `tools/call` needs a bearer token; `tools/list` does not.** Unauthenticated
   call returns "missing authentication credential". `gcloud auth print-access-token`
   works here despite the CBA warning; ADC token is the safer default for scripts.


3. **PATH B CONFIRMED — Data Products ARE groundable via lookup_context.** Earlier
   "invalid argument" on a DP resource was a DEFECTIVE call (unauth, then wrong arg
   shape), not a real rejection. With correct args + the verbatim DP name from
   search_entries, lookup_context returns rich DP context. This is the better design:
   **the wrapper gates Data Products directly — NO table->DP reverse map needed.**
   The verification unit (DP), the grounding unit (DP), and the gating unit (DP) are
   the SAME entry. Everything aligns.


4. **Table context vs DP context differ fundamentally:**
    - Table (`customers` view) context = schema, columns, timestamps, related tables.
    - DP context = the BUSINESS RULES an agent must obey, e.g. verbatim:
      "email is PII — NEVER expose in any output, session state, or briefing";
      "lifetime_value is PRE-CALCULATED — do NOT re-derive from orders table";
      segment enum; JOIN pattern; lineage chain; ingestion pipeline.
      These rules can DRIFT (a PII rule added after an agent was certified against an
      older version). An agent grounding on STALE DP context leaks PII or re-derives a
      value wrong — a CONCRETE harm, not an abstract "wrong answer". This is the demo
      payload.


5. **Related-resources auto-pull (leak to handle):** table-level lookup_context
   AUTOMATICALLY returned `relatedResources` (asked for `customers`, also got
   `orders` with full schema). So even input-side gating on requested resources can
   let unverified NEIGHBORS in via traversal. OPEN: does DP-level context also
   auto-pull related resources? If yes, wrapper needs output-side stripping too; if
   DP context is product-scoped, input-side gating suffices. VERIFY at build time.


**Search_entries returns the DP** with dataplexEntry.name =
`projects/129682754245/locations/us-central1/entryGroups/@dataplex/entries/projects/129682754245/locations/us-central1/dataProducts/ecommerce-customer-intelligence`
— this exact string is the valid lookup_context resource (doc: "same value returned
by search_entries dataplexEntry.name").


**Exclusion policy decided (Option 2):** on unverified, DROP the content from the
grounding call AND tell the agent it was excluded + why. NOT flag-and-include
(Option 3) — putting unverified CONTENT in the window with a caution is advisory and
the LLM grounds on it anyway (the exact failure the project exists to fix). Withhold
the data (structural), surface the absence (honest). Silent drop (Option 1) risks the
agent hallucinating into the gap; telling it lets the agent be honest about what it
can't speak to.


**v0.4 wrapper design (Path B):**
- MCP server (Cloud Run SERVICE, stays up) exposing a `lookup_context` tool with the
  SAME interface the agent expects.
- On call: for each requested DP resource, read its `source_tier` (via CUSTOM-view
  aspect read — the validator already wrote it). Drop unverified DPs from the
  resources[] list. Call the REAL lookup_context with the verified subset. Append an
  exclusion note for dropped DPs. (If DP context auto-pulls related resources, also
  strip unverified neighbors from the output.)
- Reads STORED verdicts (fast, data-plane). Does NOT re-run the validator per request
  (that's the scheduled slow-plane job). Control/data-plane split honored.


---


## v0.4 design question RESOLVED (19 Jul 2026, eve)


**DP-level lookup_context does NOT auto-pull related resources.** Full DP context
dumped (4696 chars): `has relatedResources: False`. DP context is product-scoped
(description, business rules, overview, lineage, sample queries incl. a self-
described freshness-check SQL) — no traversal to neighbor resources.


**Consequence: the wrapper is INPUT-GATING ONLY.** No output parsing / related-
resource stripping needed. Design fully specified, no unknowns:
agent -> wrapper.lookup_context(resources=[DP...])
-> for each DP: read source_tier (stored verdict, CUSTOM-view aspect read)
-> drop unverified DPs from resources[]
-> call REAL lookup_context (projectId+location+verified subset)
-> return context + exclusion note for dropped DPs (Option 2)
Reads stored verdicts only (data plane); does not re-verify per request.


Nice corroboration: the DP's own context contains a freshness-check SQL ("returns
FRESH or STALE, days_since_latest"). The product already declares it cares about
freshness; VCL enforces that the verification of it hasn't gone stale.


---


## v0.4 WRAPPER WORKING — structural enforcement PROVEN (19 Jul 2026, eve)


**The threshold crossed: the wrapper STOPS an agent, not just writes a flag.**


`vcl_wrapper.py` — an MCP server (stage 1 passthrough proven, stage 2 gating added)
that sits between the agent and Google's KC MCP. Input-side gating, Path B (gates
Data Products directly, no reverse map).


**Built in two stages (plumbing before logic):**
- Stage 1: pure passthrough proxy. Proven: wrapper received an MCP lookup_context
  call, forwarded to dataplex.googleapis.com/mcp with bearer auth, returned Google's
  response unchanged (context length 4696, identical to direct call).
- Stage 2: input gating. For each requested DP resource, read its stored source_tier
  (CUSTOM-view aspect read - the verdict vcl.py wrote). Drop unverified DPs. Call
  Google with the verified subset only. Append exclusion note (Option 2).


**Proven live - the full contrast, same wrapper, same request, two catalog states:**
```
STATE 1 - DP verified:
  wrapper passes through -> agent receives full 4696-char context
  (business rules incl. "email is PII - never expose", schema, lineage)


(drift the view: CREATE OR REPLACE -> etag UShI... -> MKrB...
 enforce -> technical anchor DRIFT -> source_tier written 'unverified')


STATE 2 - DP unverified:
  wrapper WITHHOLDS -> agent receives ONLY:
    "VCL: all requested resources were withheld as unverified.
     - ecommerce-customer-intelligence: excluded (unverified: source_tier=unverified)"
  No upstream call made. The DP's content - including the PII rule - never reaches
  the agent's context window.
```


**Why this is the load-bearing pivot:** everything before the wrapper WRITES a
verdict. The wrapper ACTS on it, in the agent's grounding path, structurally. The
agent cannot ground on the drifted Data Product because its content is never
returned - not flagged-and-included (advisory, ignorable), but withheld (structural).
This is the move from "sophisticated status flag" to "agent physically cannot see
unverified context."


**Config:** wrapper reads VCL_TOKEN (bearer), forwards to Google MCP, reads verdicts
via gcloud CUSTOM-view. Reads STORED verdicts only (data plane) - does not re-verify
per request (that's the scheduled validator job). Control/data-plane split honored.


**Note - base-table access:** mid-session, `bq query` on the base Iceberg table
(cross-project lakehouse-demo-...) started returning Access Denied on
bigquery.tables.getData, though it worked earlier the same day. Correct view path is
the nested `agentic-2026-493108.lakehouse-demo-agentic-2026-493108.ecommerce.customers`.
Possibly a token/identity drift (CBA vs ADC switching during wrapper work). Worth
investigating separately; did not block the wrapper proof.


**STILL AHEAD:** v2 (two ADK agents - the visible PII-leak demo, where verified agent
protects email and unverified agent would leak it); deploy wrapper as Cloud Run
service + validator as scheduled Cloud Run job; v1 Spanner seam (DM); MCP protocol
completeness (the wrapper handles tools/call for lookup_context; a real agent may
also call tools/list, initialize, etc. - stage 3 hardening).


---


## DESIGN DIRECTION — per-dimension release + semantic anchor (David's challenge, 19 Jul 2026)


**David's challenge:** the wrapper withholds the WHOLE Data Product context (incl.
business rules like "email is PII") when only the TECHNICAL anchor (etag) drifted.
Why deny the agent a PII rule that a schema-version change didn't touch?


**Current behavior (v0.4): all-or-nothing.** Any anchor drifts -> whole DP unverified
-> entire context withheld.


**Why all-or-nothing is the correct DEFAULT today (not laziness):**
1. Certification is holistic — "a steward vouched for this whole product in this
   state." When anything certified changes, you can't be sure the unchanged parts
   still hold.
2. **You cannot currently release the business rules safely, because they are NOT a
   separate anchor.** VCL verifies technical (etag) and quality (scan). The business
   rules ride along in the context blob UNVERIFIED — no fingerprint proves they're
   unchanged. Releasing them while technical drifted = asserting they're fine when
   you never checked them. That is exactly the failure the project exists to prevent.


**The upgrade David's challenge points to — per-dimension release:**
```
technical drifted   -> withhold schema/version-dependent context
semantic verified   -> release business rules (PROVABLY unchanged)
quality verified    -> release quality claims
+ tell the agent exactly what was released vs withheld and why
```
This requires a NEW anchor first: a **semantic / business-rules anchor** that
fingerprints the rules text (description/overview aspect) at seal and checks it
independently. Only then can you HONESTLY say "technical drifted but the rules are
provably unchanged, release the rules."


**The sharp caveat — ENTANGLEMENT (must respect):**
Even with a semantic anchor proving the rules TEXT is unchanged, if the SCHEMA
changed underneath them, a rule like "email is PII" may not cover a newly-added
column. Rules that REFERENCE schema are not truly independent of schema drift. So
per-dimension release is only safe where dimensions are GENUINELY independent.
Schema-vs-rules may be entangled. Guard: per-dimension release must account for
cross-dimension dependency, not assume clean decomposition.


**Honest layered conclusion:**
1. All-or-nothing = safe default when independence can't be proven (today's case).
2. Per-dimension release = better, WHEN independence is provable (needs semantic anchor).
3. Even then, watch entanglement — rules-about-schema aren't schema-independent.


**Sequence:** keep all-or-nothing for v0.4. Build semantic anchor next (fingerprint
the overview/description aspect). Then per-dimension release, WITH an explicit
cross-dimension dependency check (does the drifted dimension invalidate the
'unchanged' one?). This is a genuine trust-decomposition question — what a
verification claim scopes over, and whether trust decomposes cleanly across
dimensions.


---


## BUILD SEQUENCE — what to build when, and what NOT to build yet (19 Jul 2026)


Ranked by JOB, not wishlist. Four jobs: make it TRUE (proven), LAND (visible),
YOURS (differentiated), COMPLETE (production). Spend energy in that order. The trap:
the "complete" items (Terraform, graph, deploy) feel productive because they're
bounded and concrete, but they polish a thing not yet landed or differentiated.
Resist letting satisfying-but-lower-value work jump the queue.


**TIER 0 — prerequisite for the demo (do first, part of Tier 1):**
- **MCP protocol completeness on the wrapper.** Today it handles tools/call for
  lookup_context. A real ADK agent also calls initialize / tools/list. The agents
  won't connect without these. Harden before v2.
- **Base-table access-denial** — bq query on the cross-project Iceberg base table
  started returning Access Denied mid-session (worked earlier). Investigate before
  it bites silently. Possibly CBA-vs-ADC token drift.


**TIER 1 — makes it LAND (next, highest value):**
- **Two agents (v2).** The ONLY item that changes whether a room believes it.
  Everything built is invisible (verdicts, wrapper, tiers). Two agents make it
  visible: one grounds through the wrapper and protects "email is PII"; one grounds
  on stale context and leaks email. Same question, opposite outcome, ~30s to land.
  Nothing competes for #1.


**TIER 2 — makes it YOURS (after the demo lands):**
- **Spanner seam (v1).** Turns a DA project with a DM footnote into David's project.
  The Spanner anchor (validator meets write-never-persist scar) needs OLTP+OLAP dual
  background — the thing a generic team can't trivially replicate. Differentiation,
  which matters for L7 specifically.


**TIER 3 — makes it MORE TRUE (opportunistic, each bounded):**
- **Semantic anchor** — fingerprint the business-rules text; enables per-dimension
  release (David's challenge). Build WHEN "technical drifted but rules held" is the
  story you want to tell. Refinement, not a gate.
- **Approval-process INTEGRATION (not build).** KC ships metadata-approval ~late Q2.
  Do NOT rebuild their workflow. VCL's value is drift-invalidation, which their
  approval lacks. Integrate: seal triggered BY an approval event; VCL adds the drift
  detection. Interoperate WHEN KC ships — do not pre-build against an unshipped API.


**TIER 4 — makes it COMPLETE / PRODUCTION (last, only if the story needs it):**
- **Deploy to Cloud Run** — validator = scheduled JOB, wrapper = SERVICE. When moving
  off localhost. (Read live `gcloud run jobs/services --help`, don't trust blog syntax.)
- **Terraform** — reproducibility (aspect types, Cloud Run, scheduler) from code.
  Infrastructure packaging, not thesis. Build when handing off / for the SPARK repo.
- **Discovery graph (north-star control plane)** — build LAST, only at scale. At N=1
  hand-declaring anchors is correct; the graph finds dependencies you can't hold in
  your head, which isn't the current situation. Deferred until scale forces it —
  possibly never for a demo. Building now = the cathedral.


**One-line order:**
MCP-hardening -> two agents (LAND) -> Spanner (YOURS) -> semantic anchor ->
deploy -> Terraform ; approval = integrate-when-shipped ; graph = at-scale-or-never.


---


## Tier 0 DONE — wrapper speaks full MCP lifecycle, agent-connectable (19 Jul 2026, eve)


Hardened `vcl_wrapper.py` to proxy the full MCP handshake, not just tools/call.
Verified the real handshake sequence from the MCP spec (initialize ->
notifications/initialized -> tools/list -> tools/call) rather than guessing.


**Design: proxy everything to Google unchanged, gate ONLY lookup_context.**
- initialize, tools/list, other methods -> clean passthrough to Google MCP
- notifications (no id) -> relayed, 202, no body (per JSON-RPC)
- lookup_context tools/call -> input-side gating (drop unverified DPs)


**Session handling — turned out to be a non-issue.** Google's KC MCP reports
`serverInfo.name: "StatelessServer"`. It is STATELESS — no Mcp-Session-Id to
propagate, no sticky-session routing needed. The session-header propagation code is
harmless (no-ops when absent). One whole class of bugs avoided.


**Proven live through the wrapper:**
```
initialize  -> {capabilities:{tools:{listChanged:false}}, protocolVersion:2025-06-18,
                serverInfo:{name:StatelessServer}}   (proxied from Google)
tools/list  -> ['search_entries','lookup_context','lookup_entry']   (proxied)
tools/call lookup_context -> GATED (verified passes, unverified withheld)
```


The wrapper is now a drop-in MCP server: an ADK agent points at
http://127.0.0.1:8080/mcp instead of Google's endpoint, connects normally, discovers
the tools, and every lookup_context call is transparently gated. Tier 1 (two agents)
is now buildable — the agents can actually connect.


**SSE note:** call_google_mcp handles both plain-JSON and SSE-framed ("data: {...}")
responses from Google. Stateless + JSON has worked so far; SSE parser is there if
Google streams.


---


## CRITICAL — David's Moment-4 scenario: all-or-nothing can CAUSE the harm (20 Jul 2026)


**The scenario that reframes the demo:**
- M1: steward approves technical + quality + business metadata (incl. "email is PII,
  never expose").
- M2: technical schema drifts.
- M3: validator flips DP -> unverified.
- M4: agent calls wrapper -> DP unverified -> WHOLE context withheld, INCLUDING the
  still-valid PII rule -> agent has no "don't expose email" -> LEAKS PII.


**Why demoing M4 as a WIN backfires:** a reviewer says "your own system caused the
leak." The PII rule was fine — only the SCHEMA drifted. All-or-nothing withholding
threw away a good, safety-critical rule because an unrelated dimension changed. The
verification layer didn't prevent harm — it CREATED it. This is the earlier
all-or-nothing challenge with teeth: **withholding a still-valid safety rule because
schema changed is self-inflicted damage, not safety.**


**Consequence: the honest demo requires per-dimension release + a SEMANTIC ANCHOR.**
Two coherent, reviewer-proof stories, both requiring business rules to be an
INDEPENDENTLY VERIFIED anchor (not part of the all-or-nothing blob):


- **A (stale-rules harm, wrapper PREVENTS it):** PII rule ADDED after certification;
  agent on certified (old) context misses it; the BUSINESS-METADATA anchor drifts ->
  unverified -> withhold -> agent stopped from grounding on rules missing the new PII
  protection. Withholding is CORRECT here (rules genuinely out of date).


- **B (per-dimension release, wrapper never self-harms):** only technical drifts ->
  withhold schema-dependent context BUT still deliver the verified PII rule
  (unchanged) -> agent stays safe. Wrapper withholds only what actually drifted.


**Decision: build the SEMANTIC ANCHOR before the two-agent demo.** Fingerprint the
business-rules text (overview / description aspect) at seal; check independently.
Then:
- rules drift -> withhold rules (harm = stale rules, genuinely prevented)
- only technical drifts -> still deliver verified rules (no self-inflicted leak)


M4 proves per-dimension release + semantic anchor is REQUIRED for the demo to be
TRUE, not optional. Without it the demo either backfires (withholds a good rule,
causes the leak) or is rigged (pretends withholding-the-rule is intended safety when
it's a bug). Semantic anchor is now AHEAD of the agents in the build order.


**Entanglement caveat still applies:** even with the rules text provably unchanged,
if schema changed a rule like "email is PII" might not cover a NEW column. Per-
dimension release must check cross-dimension dependency, not assume clean split.


---


## SEMANTIC ANCHOR — why a deterministic HASH, not embeddings/RAG (20 Jul 2026)


**Source located (round-trip):** the business rules an agent grounds on ("email is
PII, never expose", pre-calc rule, etc.) live in the DP's `entrySource.description`
(545 chars, sha e59cd069...), NOT in the `overview` aspect (which is EMPTY - all
rich-text aspects on this DP are empty: overview/queries/data-stewardship/
operational-health all `data:{}`). lookup_context COMPOSES the agent context from
entrySource.description. Confirmed editable via
`gcloud dataplex entries update --entry-source-description=...`. Hash stable across
reads (e59cd069... twice). So the semantic anchor = sha256(entrySource.description).


**"Is changing the description drift?" - the precise answer:** YES, but only in the
sense the anchor MEANS: "the certified text is no longer byte-identical to what the
steward signed off on -> certification invalidated -> re-certification required." It
does NOT claim "the rules are now wrong/dangerous." Three change-kinds exist:
(1) genuine rule change (real degradation), (2) cosmetic edit (typo - meaning
identical), (3) strengthening (added protection - safer). A hash fires on all three.
That is CORRECT for a CERTIFICATION system: the steward vouched for a specific
version; any change means nobody has signed off on the new version yet. Re-cert may
take 2 seconds, but no version goes ungoverned. FRAME the exclusion note as
"certified rules changed, awaiting re-certification" - NOT "rules are unverified/bad".


**Why NOT embeddings / vector search / RAG for the anchor (David's question):**
Tempting - embeddings would let cosmetic edits pass and flag substantive changes.
But it breaks the layer for three reasons:
1. **Non-determinism:** embedding distance is a NUMBER needing a THRESHOLD (drift if
   >0.15?) with no ground truth. Different models/thresholds -> different verdicts.
   "Is this verified?" becomes a property of your tuning, not of the data. That is
   exactly the non-determinism VCL sells against.
2. **Fails on the high-stakes case:** the dangerous change is SMALL text / LARGE
   meaning. "email is PII, never expose" -> "...except for internal briefings" =
   tiny embedding distance, catastrophic meaning change. Embeddings would wave it
   through as "similar". A hash catches EVERY change including this one.
3. **Model in the trust path:** an embedding model has versions, drifts, can be
   updated under you. If the verdict depends on a model, verification is only as
   trustworthy as that model. VCL's pitch ("a deterministic verifier you trust MORE
   than the AI it checks") collapses if the verifier contains AI.


**The identity vs similarity distinction:** embeddings answer "how similar in MEANING
are these texts?" (fuzzy, non-deterministic). The anchor asks "is this the EXACT
artifact the steward certified?" (crisp, provable). Certification is an IDENTITY
question - hashing answers it perfectly, embeddings answer it badly. Using a
similarity tool for an identity question is the mismatch.


**Where embeddings DO belong (David's instinct, relocated one step):** NOT in the
verdict, but in TRIAGE/discovery to help the human RE-CERTIFY faster. When the hash
anchor fires, a human must look. Embedding similarity can ADVISE that human: "98%
similar - probably cosmetic, quick re-approve" vs "diverged significantly - look
carefully." That is embeddings ADVISING a human (control plane, advisory, non-
determinism OK), not MAKING the verdict (data plane, must be provable). Same
control/data-plane discipline: deterministic hash = trust boundary; embedding-diff =
triage aid, human-in-loop. NOTED as a future enhancement; the anchor itself stays a
hash.


---


## SEMANTIC ANCHOR — target correction + LLM-triage layer (20 Jul 2026)


**Finding: entrySource.description is NOT editable on a first-party DP.**
`gcloud dataplex entries update --entry-source-description` -> 400 "entry_source
cannot be updated in first party entries." Business rules ("email is PII, never
expose") live in the DP `description` field, which is UI-IMMUTABLE. Separately, a
`documentation` field IS UI-editable (and Gemini-generatable). BOTH are composed into
what lookup_context returns.


**Design correction: fingerprint the COMPOSED lookup_context output, not
entrySource.description alone.** The agent grounds on the whole composed context
(4696 chars), which blends the immutable description (PII rule) AND the mutable
documentation. Fingerprinting only description would MISS drift in documentation
(regenerate docs -> bad instruction -> agent grounds on it -> anchor wrongly says
verified). Composed-context fingerprint covers both = fingerprints exactly what the
agent receives.
- Stability CONFIRMED: composed context sha = 5320ea1640c8066b, stable across repeated
  calls (no volatile timestamps/ordering in the text). Valid fingerprint.
- Demoable drift path: edit `documentation` in the UI (or regenerate with Gemini) ->
  composed context changes -> sha moves -> semantic drift. This is the real steward
  workflow, better than a CLI edit.
- TODO next session: re-point vcl.py semantic anchor from read_business_rules
  (entrySource.description) to a read of the composed lookup_context output; re-seal;
  prove semantic drifts alone when documentation edited, technical+quality hold.


**LLM for semantic drift — resolved (David pushed hard, correctly):**
David's point: a pure hash is too blunt — invalidating the whole semantic context
because someone added a comma/title is foolish. CORRECT. But the fix is NOT making an
LLM the verdict:
- **Temperature 0 does NOT give determinism.** Greedy decoding still rides on
  non-bitwise-reproducible GPU float math (non-associative reductions, kernel/batch
  variance); near-tied tokens flip. Plus the model gets silently updated underneath
  you. Temp 0 = usually-stable, not provably-stable. "Usually" is disqualifying for a
  trust boundary.
- **Adversarial case:** "never expose" -> "never expose unless internal" is
  semantically tiny / catastrophically important. An LLM classifier may rate it
  "minor clarification" and PASS it. A hash catches it (bytes changed).
- **Quis custodiet:** if the verifier is an LLM, "why trust the verifier?" answers
  "it's a smaller LLM" — collapses VCL's whole pitch (trust the verifier MORE than the
  AI it checks).


**Resolution — LAYER, don't replace:**
1. Deterministic HASH = the TRIGGER (any byte change -> "certified text changed").
   Cheap, provable, catches everything incl. the comma-sized meaning bomb. Trust
   boundary; must be deterministic.
2. Hash change does NOT auto-invalidate forever -> it opens a RE-CERTIFICATION task.
   Re-confirming a comma = 2 seconds.
3. LLM = TRIAGE ASSISTANT on that task: shows human old-vs-new, advises "cosmetic,
   one-click re-approve" vs "rule changed, review carefully." LLM ADVISES; human (or
   deterministic re-seal) CERTIFIES. LLM never in the verdict path.
   This keeps David's insight (don't nuke on a comma) AND the guarantee (verdict
   provable). David's instinct was almost the right architecture — the fix is the LLM
   raises it to a HUMAN for re-cert, not as the system's verdict. Future enhancement;
   anchor stays a hash.


---


## ARCHITECTURAL LAW — context is whole-or-nothing (David, 20 Jul 2026)


**The semantic anchor is re-pointed and PROVEN:** now fingerprints the COMPOSED
lookup_context output (sha 5320ea16, stable), not entrySource.description alone.
Covers both the immutable `description` (PII rule) and the UI-editable `documentation`
(Gemini-generatable). Proven live: edited documentation in UI -> semantic anchor
DRIFTED ALONE (technical + quality stayed green) -> UNVERIFIED (1 of 3). Per-dimension
INDEPENDENT drift confirmed through the real steward workflow. Three dimensions
(technical/quality/semantic) all working. Added --dp-resource CLI arg.
(Bug caught: an over-broad sed added dp_resource to read_dp_assets too; runtime
TypeError caught it; fixed.)


**Then the design question: should per-dimension release DELIVER verified dimensions'
context while withholding drifted ones? David's decisive answer: NO.**


**David's argument (retires a whole branch of complexity):** delivering technical
context (schema) while stripping semantic context (rules) hands the agent columns
with NO governance — it sees `email`, `lifetime_value` as raw schema with none of
"email is PII" / "don't re-derive". The agent then GUESSES to fill the gap. And the
WRAPPER created that dangerous half-context. The fault moves from "steward has an
un-recertified rule" (governance state the steward OWNS) to "wrapper delivered
misleading partial context" (fault the WRAPPER introduced). Confident-but-ungoverned
is MORE dangerous than blind: a context-less agent knows it's blind; a
schema-without-rules agent thinks it's informed and acts confidently on ungoverned
columns.


**THE LAW:** Context is delivered WHOLE or NOT AT ALL. The wrapper never hands an
agent a partial context, because a partial context is a MISLEADING context. The
wrapper's only two moves: deliver the full verified context, or withhold it entirely
and say why.


**Consequences (simplifies everything):**
- Unit of verification = unit of delivery = the whole Data Product's context. No
  slicing. No context decomposition engine. No fingerprint-the-rules-portion re-point.
- The entanglement problem (technical->semantic edge, "does schema change break the
  rule") no longer needs to be SOLVED to decide delivery — because delivery is
  whole-or-nothing regardless. Entanglement only matters for the DIAGNOSIS/triage,
  not the gate.
- Per-dimension VERDICT still matters — for telling the steward WHICH dimension
  drifted and why, so re-cert is targeted. Dimensions are separate in the DIAGNOSIS,
  unified in the DELIVERY decision.


**Reconciling Moment-4 with this law:** Moment-4 = "all-or-nothing withholds a good
rule, bad." This law = "partial delivery misleads, worse." Synthesis: withhold-WHOLE
is correct; the badness of all-or-nothing was the SILENCE, not the withholding. Fix =
withhold whole context + LOUD, FAST, LLM-triaged re-certification. Steward owns the
fix; wrapper never fakes a partial picture.


**Consequence for the build:** the wrapper ALREADY does whole-or-nothing withhold. It
only needs a RICHER DIAGNOSIS (name which dimension(s) drifted in the exclusion note),
NOT a decomposition engine. David's safety argument SIMPLIFIED the build — a whole
branch (context decomposition, per-section fingerprinting, technical/semantic split
delivery) is retired.


**Final wrapper logic:**
read all dimension verdicts
ALL verified -> deliver full context
ANY drifted  -> withhold FULL context (never partial)
-> exclusion note names WHICH dimension(s) drifted + why
(steward's targeted re-cert signal; LLM-triaged later)


---


## CORRECTION to the whole-or-nothing law (Claude pushback, 20 Jul 2026)


On re-examination, "whole-or-nothing" as stated was over-generalized. Two fixes:


**1. Within-DP vs across-DP.** David's argument proves: WITHIN a single DP's composed
context, you cannot split rules from schema (partial single-context = misleading).
CORRECT. But it does NOT prove the wrapper is all-or-nothing across EVERYTHING.
Multi-DP case: agent requests [Customers(verified), Orders(verified),
Marketing(drifted)]. Withholding all three because Marketing drifted = collateral
denial, not safety. Correct rule:
- WITHIN one DP's context: atomic, whole-or-nothing (never a partial single-context).
- ACROSS DPs: per-DP. Each DP independently whole-or-withheld. Unit = the DP.
  This is what the wrapper ALREADY does (gates per-resource in resources[]). So the law
  is a PER-DP ATOMICITY rule, not "any drift withholds everything."


**2. Justification correction.** "The wrapper manufactured the hazard" proves too much
— withholding ALSO changes agent behavior (guess/refuse), so the wrapper influences
the outcome in EVERY case incl. withholding. The defensible argument is narrower:
partial delivery is worse than withholding because it is CONFIDENTLY MISLEADING
(schema without governance -> agent thinks it's informed, acts on ungoverned columns)
rather than OBVIOUSLY BLIND (no context -> agent knows it's blind). "Misleading beats
blind" is the real principle, not "wrapper caused it."


Net: David's core instinct holds (no partial single-context), but the precise law is
"per-DP atomicity, justified by misleading-beats-blind" — not a blanket
all-or-nothing across all requested resources.


---


## BUG FIX — quality scan executionStatus fields not guaranteed present (20 Jul 2026)


**Live-caught:** a re-seal produced `seal quality = PASS@None` — the quality fingerprint
captured a None timestamp. Traced to the scan API: `datascans describe` on
customers--quality returned `state: ACTIVE`, `dataQualityResult.passed: True`, but
`executionStatus` contained ONLY `latestJobCreateTime` — NO `latestJobEndTime`, NO
`latestJobStartTime`. Earlier the same scan returned latestJobEndTime=06:47. So
executionStatus fields are NOT guaranteed present; latestJobEndTime can vanish between
reads of the same scan even with a valid passing result.


**Fix (read_scan_quality + quality_fingerprint):**
- Prefer latestJobEndTime; fall back to latestJobCreateTime; if NEITHER exists, return
  an error and SKIP the quality anchor (never seal a None-timestamp fingerprint).
- Fingerprint now encodes the timestamp SOURCE: `PASS@end:<iso>` or `PASS@create:<iso>`.
  This means a check compares like-with-like and won't false-drift merely because the
  available timestamp field changed between seal and check.
- Confirmed: re-seal now shows `PASS@create:2026-07-20T12:30:34...` (real, labeled),
  not PASS@None.


Discipline note: the terminal showed PASS@None; we did NOT seal over it — traced to
the API, hardened the code, re-verified. Round-trip caught a bug that would have
caused phantom quality drift on the next check.


## LIVE VALIDATION of the comma problem (20 Jul 2026)
David added ONE COMMA to the description. Semantic hash moved 5320ea16 -> bbac76fe.
Against the old seal this would fire semantic DRIFT -> UNVERIFIED -> whole context
withheld. This is EXACTLY the over-firing David challenged. He judged the comma benign
and re-sealed — i.e. he manually PERFORMED the human-in-the-loop re-certification the
design calls for. The LLM-triage layer would automate the "is this benign?" ADVICE to
the steward; the judgment + re-seal stay human. The architecture (hash fires, human
re-certifies, LLM triages) validated by a real cosmetic edit.


---


## PRODUCTION-READINESS AUDIT — hardcoded vs discovered (David's question, 20 Jul 2026)


David asked: are we hardcoding assets / the Data Product? For production we must not.
Honest audit:


**NOT hardcoded (production-ready):**
- vcl.py ASSETS: auto-discovered from the DP's own data-product.assets[] manifest.
  Pass the DP, it reads its own assets. No asset hardcoding. (The v0.3c refactor.)
- DP identity: passed as CLI args, not baked into the file.


**Hand-supplied in the demo (NOT production-ready as-is):**
1. QUALITY-SCAN MAPPING (`--quality-scan customers=customers--quality:24`): the human
   declares which scan verifies which asset, per DP. Does NOT scale to N DPs. This is
   the DEFERRED discovery problem resurfacing — production should DISCOVER the
   DP->scan mapping (walk catalog, match scan data.resource to the DP's assets), not
   be told it. = the north-star control/discovery plane, again.
2. DP identity + --dp-resource string: CLI args now; production iterates search_entries
   over all DPs. EASY (a loop) - CLI ergonomics, not an architectural flaw.
3. Wrapper VCL_PROJECT/LOCATION/ASPECT_TYPE: single env set; assumes all DPs share one
   project/aspect-type. Production needs per-DP resolution. MODERATE.


**Boundary (state honestly when presenting):**
assets            -> auto-discovered      [production-ready]
DP identity        -> CLI arg -> loop over search_entries   [easy]
dp-resource        -> CLI arg -> from search_entries        [easy]
quality-scan map   -> MANUAL -> catalog discovery           [the deferred graph]
wrapper proj/aspect-> single env -> per-DP resolution       [moderate]


Fix is NOT "hardcode differently" - it's: keep demo hand-supplied AND honest about it;
mark scan-discovery + DP-iteration as the production step (same deferred discovery
plane). Serves Principle 6 (candor): when asked "does it scale?", the answer is a
precise seam, not hand-waving. Do NOT build discovery now (deferred, at-scale work).


---


## WRAPPER DIAGNOSIS COMPLETE — drift_summary + honest agent note (20 Jul 2026)


**Two-file coordinated change, built one-at-a-time and verified between (no format
mismatch):**


**vcl.py side (proven first):** enforce now writes `drift_summary` (which dimensions
drifted, e.g. ["semantic"]) into the claim alongside source_tier; seal clears it to
[]. Schema v6 added `drift_summary` (array of string), validated + applied. Proven
round-trip: drift semantic -> enforce -> `drift_summary=['semantic']` ->
read-back `source_tier: unverified, drift_summary: ['semantic']`. The array persisted
(no write-never-persist issue on this @dataplex path).


**Wrapper side:** read_source_tier now returns (tier, drifted_dims, err). The exclusion
note is enriched from a generic "unverified" to a targeted, honest message telling the
agent: STATE (unverified) + REASON (which dimension drifted, from drift_summary) + HOW
TO BEHAVE (don't ground/infer/fabricate; if asked, explain re-certification pending).


**Proven live (DP unverified, semantic drifted):**
```
VCL: all requested resources were withheld.
VERIFICATION STATUS: unverified.
... withheld ... because their certification is no longer current:
  - ecommerce-customer-intelligence: semantic drifted - re-certification pending
Do not ground on, infer, or fabricate details about the withheld resource(s). If the
user asks about them, explain that the data product's context is pending
re-certification and cannot be used until a steward re-verifies it.
```


**Design discipline (David's point):** the note must tell the agent the STATE and WHY,
not just "excluded", so a well-behaved agent responds honestly to the user instead of
guessing. BUT: the note is ADVISORY (an LLM can ignore "don't fabricate"). The
STRUCTURAL guarantee remains the WITHHELD CONTENT (absent -> ungroundable). Note =
courtesy for graceful degradation; absence = the actual enforcement. Never rely on the
note for safety.


This completes the wrapper's per-DP diagnosis. Wrapper now: whole-or-nothing per-DP
gate (structural) + stored-verdict read (fast, no per-request re-verify) + targeted
honest re-cert signal (names the drifted dimension). Files: vcl.py, vcl_wrapper.py,
verification_v6_driftsummary.json.


---


## WHY NO VECTOR DB / EMBEDDINGS FOR TRIAGE — sizing reasoning (20 Jul 2026)


Decision: the semantic re-certification TRIAGE is LLM-only. No vector database, no
embedding index. This is architecturally correct, not a "small for now" shortcut.
The reasoning is worth recording because it justifies the design and pre-empts the
reviewer question "why not embeddings?"


**What would be indexed (get this right first):** NOT the data, NOT rows — the
BUSINESS-RULE TEXT / documentation of Data Products. So the sizing question is: how
many Data Products, each with how much rule text, does a real org have?


**Realistic sizing:**
- Data Products are CURATED, GOVERNED assets (each a deliberate act of curation).
  A large enterprise has HUNDREDS to LOW-THOUSANDS of them (order 500-5,000), NOT
  millions.
- Each DP's rule text is SMALL (our description = 545 chars; docs maybe a few KB).
- Entire business-metadata corpus across a large org: thousands of DPs x a few KB =
  single-digit to low-tens of MB of text. Tiny. Fits in a Python dict, in memory.


**The decisive point — it's the JOB, not the size.** The triage's job is: when ONE
DP's rules drift, compare THAT DP's OLD text vs its NEW text and advise the steward
(cosmetic vs substantive). That is:
- ONE pairwise comparison (old vs new of a single DP),
- triggered occasionally (when that DP changes),
- NOT a search across a corpus.


A vector DB earns its place for SIMILARITY SEARCH ACROSS A LARGE CORPUS ("find the 10
most similar of a million"). The triage does not search a corpus — it compares TWO
specific short strings. That is a single pairwise cosine on two vectors. No index, no
store, no DB. **A vector database is the wrong tool for the triage at ANY scale**, not
because the org is small, but because the job is PAIRWISE COMPARISON, not corpus
search. Standing up a vector DB to compare two strings would be infrastructure theatre.


**Why LLM DOES make sense here (the contrast):** the triage question is "did the
MEANING change, and which rule?" — comprehension of arbitrary, customer-authored rules
("salary is confidential", "GDPR-restricted"). That is language understanding, which
is exactly the LLM's job, and it needs no corpus and no hardcoding. Send old text +
new text -> "cosmetic / substantive / which rule changed." Pairwise, on-demand,
advisory. (And it stays OUT of the verdict — the deterministic hash is still the
trigger; the LLM only advises the human's re-seal.)


**Where a vector DB WOULD be justified (a DIFFERENT job, deferred):** DISCOVERY — "find
all DPs whose rules are semantically RELATED to this one" (e.g. all PII-handling DPs,
to re-check when regulation changes). THAT is corpus similarity search and could
justify a vector store at thousands of DPs. But that is the DISCOVERY / control plane
(the north-star graph), gated on having many DPs AND a discovery use case — deferred,
possibly never for a demo. Not the triage.


**Net:** triage = LLM-only, pairwise, advisory. Embeddings might LATER appear as a
cheap pairwise pre-filter (embed 2 strings, skip the LLM if cosine ~0) — an
optimization, still two vectors and no DB. Vector DATABASE only enters with corpus
DISCOVERY, which is a separate, deferred plane. The size-independent rule:
pairwise-compare -> LLM (or 2-vector cosine); corpus-search -> vector DB. The triage is
pairwise. Hence LLM.


---


## IAM / SERVICE-ACCOUNT DESIGN (20 Jul 2026)


Pattern: each Cloud Run component runs as a DEDICATED, least-privilege service
account (SA), attached to the Cloud Run job/service. No user creds, no keys. Three
components have three DISTINCT permission profiles — ideally three separate SAs so a
compromise of one does not grant another's access (notably: only the triage SA can
call a model).


**Validator (vcl.py) — Cloud Run JOB SA:**
- bigquery.tables.get         (read view etag = technical anchor)
- dataplex.datascans.get      (read DQ scan result = quality anchor)
- dataplex.entries.get        (read DP manifest, assets, business rules)
- dataplex.entries.update / aspect write  (write source_tier, drift_summary, anchors)
- (calls lookup_context for semantic anchor -> dataplex read, covered above)
  Roughly: a scoped Dataplex read/write + BigQuery metadata read. Read-heavy, one write
  path (the verification aspect).


**Wrapper (vcl_wrapper.py) — Cloud Run SERVICE SA:**
- dataplex.entries.get        (read stored verdict: source_tier + drift_summary)
- dataplex lookup_context     (proxy to Google MCP = dataplex read)
- NO writes. NO Vertex. NO BigQuery data access.
  Least-privilege: read-only catalog. If compromised, cannot alter verdicts or call a
  model.


**Triage (new, LLM) — Cloud Run JOB/SERVICE SA:**
- dataplex.entries.get        (read old/new rule text)
- **roles/aiplatform.user**   (aiplatform.endpoints.predict — call Vertex AI Gemini)
  The ONLY component with Vertex/model access. Isolate it: the cost- and model-bearing
  permission lives on exactly one SA. A wrapper or validator compromise does NOT reach
  the model.


**Principle:** the model-calling permission (aiplatform.user) is the most sensitive
(cost + model access) and is confined to the single component that needs it (triage).
Verdict-writing (aspect update) is confined to the validator. The wrapper — the
internet-facing, agent-connected surface — is READ-ONLY, so the most-exposed component
has the least privilege. Document these grants explicitly (Terraform later); never run
any component as a broad/admin identity.


TODO: confirm exact predefined-role vs custom-role choice against current docs at
deploy time (e.g. is roles/dataplex.metadataReader + roles/dataplex.entryGroupOwner
the right split, or a custom role). Do NOT assume role names — verify live before
granting.


---


## SEMANTIC TRIAGE WORKING — LLM-advisory, comma problem solved (20 Jul 2026)


Built `vcl_triage.py` (standalone v1): compares OLD vs NEW business-rule text, advises
the steward cosmetic vs substantive. LLM-only (no vector DB - pairwise job). Uses the
current google.genai unified SDK (v2.9.0 installed), vertexai=True, gemini-2.5-flash,
temp 0. ADVISORY ONLY - never writes source_tier, never re-seals, never gates. The
deterministic hash stays the trigger + verdict; the LLM only informs the human's
re-seal decision.


**IAM prediction CONFIRMED live:** first run (as user ADC, no Vertex role) returned
`403 PERMISSION_DENIED, permission 'aiplatform.endpoints.predict' denied on
.../models/gemini-2.5-flash`. This is the EXACT permission the IAM design doc said the
triage needs (roles/aiplatform.user grants aiplatform.endpoints.predict). The design
predicted it; the system confirmed it to the exact permission string. Candor loop
working: documented the requirement, then proved we needed exactly that. Fixed via
`gcloud auth application-default login` (user has Vertex access on this project).
Production: dedicated triage SA with roles/aiplatform.user (per IAM doc).


**Comma problem SOLVED (the thing David flagged hours ago):**
Input: period -> comma. Triage output:
classification: cosmetic; changed_rules: []; recommendation: one-click re-approve;
reasoning: "only punctuation ... does not alter meaning".
So: deterministic hash FIRES on the comma (correct - detects any change), triage
instantly says "cosmetic, one-click re-approve". The over-firing David worried about is
now MANAGEABLE: fires deterministically, resolves in seconds. This is the layer that
makes hash-based semantic drift production-sane instead of brittle. It is also the
answer to the reviewer objection "so any typo breaks your system?" - no, it flags and
the triage clears it in one click.


**Substantive case PROVEN (the dangerous edge - Test 2):**
Input: "never expose" -> "never expose, except for internal briefings". Triage output:
classification: substantive; changed_rules: ["email column exposure rule"];
recommendation: review carefully before re-certifying;
reasoning: "introduces an exception to the 'never expose' condition ... changes the
permissible exposure of PII".
It caught EXACTLY the small-text/large-meaning change that defeats the alternatives:
- pure HASH: "text changed" - treats comma and exception-clause identically, can't
  distinguish safe from dangerous.
- EMBEDDINGS alone: the two strings are ~95% token-identical -> tiny distance ->
  would likely pass it as "minor". MISSES it.
- TRIAGE (LLM): understands "except for internal briefings" punches a hole in a PII
  rule -> substantive -> names the rule -> review carefully.
  Two tests together prove the discrimination that is the whole point: cosmetic edits
  clear instantly (one-click), dangerous semantic weakenings get flagged for review.
  This validates: deterministic HASH triggers (catches everything), LLM TRIAGES
  (cosmetic vs substantive), HUMAN decides. The comma-over-firing problem AND the
  subtle-weakening problem are both solved, with the verdict staying deterministic.
  Files: vcl_triage.py.


---


## TRIAGE ARCHITECTURE — separate file, atomic via hash-pinning (David, 20 Jul 2026)


**vcl_triage.py stays SEPARATE from vcl.py. The file boundary encodes the trust
boundary:**
- vcl.py = deterministic core, must stay PROVABLY AI-FREE. No `import google.genai`.
  You can point at it and say "no model, no Vertex, nothing non-deterministic." Own
  service account: Dataplex + BigQuery, NO aiplatform.user.
- vcl_triage.py = advisory human-assist, ALLOWED to be AI. Own service account WITH
  roles/aiplatform.user. If merged, the deterministic verifier's SA would carry
  needless Vertex access (violates least-privilege) and the file would contain an LLM
  import (breaks the provably-AI-free property).
- Different lifecycle: vcl.py runs unattended on a schedule (Cloud Run JOB); triage
  runs on-demand for a HUMAN deciding whether to re-certify.
- They communicate through CATALOG DATA (the drift record), NEVER a Python import.
  vcl.py records the drift; triage is invoked separately against it. Decoupled.
  This is "structural over instructional": rather than DOCUMENTING "the verifier is
  deterministic", make it structurally impossible for the verifier to be
  non-deterministic by keeping the LLM in a different file with a different identity.


**THE RACE CONDITION David caught (why separation needs care):** the triage compares
old-vs-new, but "new" is a moving target. If someone edits docs AGAIN between drift
detection and triage:
enforce@T1: old=A, current=B, records "drifted"
steward edits@T2: current now C
triage@T3: compares A vs C, but the VERDICT was about A->B.
Result: steward re-certifies C while reading advice about B - re-certifies a version
the triage never evaluated. Integrity hole.


**Requirement (David):** verdict and triage MUST be about the SAME version. Atomic.


**FIX - atomicity via HASH-PINNING (deterministic, no lock):** the fingerprint IS the
version identity. On semantic drift, vcl.py records BOTH fingerprints - sealed (old A)
and drifted (new B) - into the drift record. The triage:
1. reads current text, hashes it,
2. MUST equal the recorded B (the version the drift was about),
    - matches -> current text IS the drift's version -> safe to triage,
    - mismatch (edited again -> current=C!=B) -> REFUSE: "text changed again since
      drift detected; re-run enforce first."
3. compares A vs B, advises.
   The hash-match IS the atomicity enforcement. No shared lock, no transaction - the hash
   pins the version. Same discipline as everywhere: don't ASSUME versions match, PROVE it
   by round-tripping the hash before acting. The triage is bound to a SPECIFIC drift
   event, not "current state"; to triage a later edit, re-run enforce (re-pins B), then
   triage.


**Data-model additions this requires (real, not free):**
- store the OLD rule TEXT in the anchor at seal (not just its hash) - so the triage
  can show "A -> B", needs text-A, not only hash-A.
- store the NEW text + its hash in the drift record at enforce - so B is pinned.
- triage reads current -> hashes -> must equal B -> compares A vs B.
  (Schema consideration: rule text is a few KB; storing it in the anchor is fine. Or
  steward supplies old text from git/snapshot - but in-anchor is cleaner for the atomic
  guarantee.)


This is what makes SEPARATE files SAFE to run independently: they cannot disagree
about which version, because the hash forces agreement-or-refusal. David's atomicity
requirement drove the correct design, same pattern as the whole-or-nothing law.


---


## ATOMICITY BUILT + certified_text decision (20 Jul 2026)


**Atomicity gate PROVEN.** Schema v7 added drifted_hash (string) + drift_detected_at
(datetime). enforce writes the pin on semantic drift; seal/verified clears it; triage
gates on it.
- enforce wrote: `drifted_hash pin = sha256:4839b297...`
- triage: `GATE OK: current context matches the pinned drift version` before advising.
  The version-match atomicity runs: triage only advises on the version the verdict
  pinned; refuses if current != pin (re-run enforce).


**Bug caught (KC constraint):** datetime fields CANNOT hold "". Setting
drift_detected_at="" -> 400 "Text '' could not be parsed at index 0". Fix: OMIT the
datetime field when clearing (absent, not empty); KC preserves absent optional fields.
String fields (drifted_hash) accept "" fine. Rule: string can be ""; datetime must be
absent-or-valid.


**David's confusion -> a real design fix.** Triage reported a big list of changes for
"I only added a comma." Cause: `--old` was `/tmp/original_rules.txt` = the WEEKS-OLD
original (full rules incl. PII), saved this morning; the current description had been
edited down during today's tests. So the diff was ancient-original -> now, not
last-comma -> now. The triage was CORRECT; the hand-supplied `--old` baseline was
wrong. This proves hand-supplied old-text is unreliable: the steward can paste the
wrong baseline.


**FIX: store certified_text in the anchor at seal.** The triage's `old` must be the
EXACT last-certified version - only VCL reliably has that. Storing it makes both sides
of the diff come from VCL's pinned state (old = certified_text from anchor, new =
pinned current via the gate), neither hand-supplied. Then "added a comma" -> triage
shows just the comma.


**WHERE to store certified_text: the KC aspect. NOT Firestore/Spanner.** (David asked.)
- Co-located with the verdict: comes back in the SAME read as the pin (one gcloud
  call). Firestore/Spanner = two reads, two failure points, two IAM grants, and the
  version-skew problem we just solved returns ACROSS a store boundary (aspect says
  hash-A, Firestore has text-B). Same-aspect = written together, read together, can't
  skew.
- Size: few KB/DP x thousands of DPs = single-digit MB. Aspects hold this fine.
- Same discipline as "no vector DB": don't add infrastructure the job doesn't need.
  The job is "store one value, read it with the verdict" = a field in a record we
  already read.
- **Future note (correct placement):** Firestore IS the right home LATER for
  certification HISTORY/AUDIT (append-only: every certified version over time, who
  approved) - the aspect holds only CURRENT state. Not built now; noted.


**Next:** schema v8 add certified_text (string) to the anchor (or top-level); seal
stores current composed context text; triage reads it as `old` instead of a
hand-pasted file.


---


## certified_text COMPLETE — atomicity closed on both sides (20 Jul 2026)


Schema v8 applied (certified_text, string). Bug en route: the apply step was skipped
(the "# then apply" line pasted as a comment) -> seal hit `400 Unknown property:
certified_text` because the field wasn't in the applied schema. Lesson: validate-only
!= apply; confirm the field appears in describe before writing it. Re-applied for real,
certified_text present, seal succeeded.


**PROVEN end-to-end (the David-confusion fix):**
seal (stores certified_text = current composed context)
-> add ONE comma in UI
-> enforce (drifted_hash pin = sha256:ccf11700...)
-> triage --dp-entry/--dp-resource, NO --old:
GATE OK: current matches pinned drift version
(using stored certified_text as the OLD baseline)
classification: cosmetic; reasoning: "only punctuation and spacing ... between
two existing bullet points ... without altering meaning"; one-click re-approve.
This time it showed JUST the punctuation change - because `old` came from the
certified_text stored at THIS seal, not the weeks-old /tmp/original_rules.txt. The
wrong-baseline error is now STRUCTURALLY IMPOSSIBLE: both diff sides come from VCL
state (old = stored certified_text, new = pinned-verified current), neither
hand-supplied.


**Atomicity now closed on BOTH sides:**
- NEW: pinned at enforce (drifted_hash); gate verifies current==pin, refuses if moved.
- OLD: stored at seal (certified_text); the exact last-certified baseline.
  The triage advises on a provable, self-consistent version pair. Hand-supplied --old
  remains as an override/fallback but is no longer needed.


VCL CORE COMPLETE: validator (3 dims + drift_summary + atomicity pin + certified_text),
wrapper (whole-or-nothing gate + honest note), triage (LLM advisory + atomicity gate +
stored baseline). All proven live. Schema at v8. Remaining: two-agent demo; deploy;
Firestore audit-history (future); discovery plane (deferred).


---


## DEMO AGENT DESIGN — audience builder, enforcement in the TOOL not the prompt (20 Jul 2026)


Chose the demo agent: a CAMPAIGN AUDIENCE-BUILDING agent (not a QA/RAG agent - "we have
SQL and databases for that; people will laugh at L7"). It builds a win-back marketing
audience, which INHERENTLY needs the customer Data Product (can't build a customer
audience without customer data). Agentic: authors + executes SQL, produces a persistent
export artifact. The governance stake is the EXPORT BOUNDARY - once email leaves for an
external marketing tool it can't be recalled (the classic real PII-exfiltration
incident).


**Two tools, both gated by verification (structural on BOTH sides):**
- Tool 1 = governed context via the VCL wrapper (McpToolset + StreamableHTTP). Verified
  -> delivers context incl. which SAFE view to use; unverified -> withholds.
- Tool 2 = BigQuery action tool. David caught that the FIRST draft enforced the
  unverified case INSTRUCTIONALLY ("if withheld you MUST NOT query") - the exact
  Principle-1 failure. FIX: move enforcement OUT of the prompt INTO the tool. Tool 2
  itself READS the DP verdict (same source_tier the wrapper reads) and REFUSES to
  execute against an unverified DP's data, regardless of what the agent asks. The agent
  instruction drops to EXPLANATION-ONLY (tell the user re-cert is pending); it enforces
  nothing.


**Result: verification gates BOTH reading context AND taking action, structurally, in
both tools.** The agent's prompt is naive about VCL and enforces nothing. This is the
door principle on both sides: the governed path is the only path. Consistent with
Principle 1 (structural over instructional) on the action side, not just the read side.


**Structural surface (verified live):**
- Safe view `ecommerce_views.customers_safe` = [customer_id, country, city,
  signup_date, customer_segment, lifetime_value] - NO email/first_name/last_name
  (schema-read confirmed). Created today.
- `ecommerce_views.customers` HAS email (locked out). `ecommerce_views.orders` = join
  target. Base `ecommerce` dataset doesn't exist (data is behind Iceberg views).
- So customer_id is the audience identifier; email never enters the export - the real
  governed marketing pattern (build by ID, send inside the governed platform).


**Two structural layers on the action:**
1. customers_safe has no email BY CONSTRUCTION (column safety).
2. Tool 2 refuses to execute at all when the DP is unverified (verification gate).
   So: verified -> agent queries customers_safe, builds PII-safe audience, executes.
   Unverified -> Tool 2 refuses (reads verdict) -> no audience -> instruction only explains.


**Demo:** ONE agent, ONE brief, run TWICE, catalog verification state the only variable.
author-and-present: EXECUTE only the safe verified path; NEVER execute a PII query;
show the danger by contrast. Safe-view already exists; tool-level verdict-check is the
scoping (option B-light); IAM-scoped SA is the documented production hardening.


Spec files (for the context-engineering harness): requirements.md, lesson.md,
exercise.md, plan.md. Verified ADK wiring: McpToolset +
StreamableHTTPConnectionParams(url, headers) from google.adk.tools.mcp_tool.*. Flagged
[VERIFY] (not guessed): ADK Runner API, exact BigQuery tool construct, LlmAgent import.


