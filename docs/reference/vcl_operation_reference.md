# VCL Operations Reference — who calls what, when, why


The verified-live map of every VCL entry point. Columns: **WHAT** (the operation),
**WHEN/STAGE** (at which point in the lifecycle), **HOW** (the actual command +
key params), **WHY** (what it achieves), **WHO** (the actor/process that triggers it).


Extracted from the live code (vcl.py, vcl_triage.py, vcl_wrapper.py) on 2026-07-20,
not from memory. Schema at v8.


---
**Author:** Wissem Khlifi ·


**July 2026**


## The lifecycle in one line


```
[schema apply] --once per schema change-->  seal --steward certifies-->  check/enforce --scheduled, detects drift-->  triage --steward reviews drift-->  seal again --re-certify-->
                                                                              wrapper --every agent request, gates on stored verdict-->
```


---


## 1. Schema apply — `gcloud dataplex aspect-types update verification`


| Field | Detail |
|---|---|
| **WHAT** | Applies/updates the `verification` aspect-type schema (the shape of the record VCL writes) in Knowledge Catalog. |
| **WHEN** | ONCE per schema change (rare). NOT part of the runtime loop. Only when a new field is added (v6 drift_summary, v7 drifted_hash/drift_detected_at, v8 certified_text). |
| **HOW** | `gcloud dataplex aspect-types update verification --location=us-central1 --project=$PROJECT_ID --metadata-template-file-name=verification_v8_certtext.json` — run `--validate-only` FIRST, then WITHOUT it to apply. |
| **WHY** | KC rejects any aspect write containing a field not in the applied schema (`400 Unknown property`). The schema must exist before seal/enforce can write the field. |
| **WHO** | The developer/steward, by hand, at build time. Never automated, never in the request path. |
| **GOTCHAS** | `--validate-only` != apply (validation passing does NOT change the schema). Confirm with `describe` that the field appears before writing it. Additive fields only (append-only, safe). datetime fields cannot be `""` — omit when clearing. |


---


## 2. `vcl.py seal` — steward certifies


| Field | Detail |
|---|---|
| **WHAT** | Captures the current fingerprints of all 3 dimensions and writes a `verified` claim: anchors (technical/quality/semantic), `source_tier=verified`, `certified_text` (the composed-context baseline), clears drift pin. |
| **WHEN** | (a) Initial certification of a Data Product. (b) RE-certification after a steward reviews a drift and accepts it. This is the "human signs off" moment. |
| **HOW** | `python3 vcl.py seal --project --project-number --location --entry-group --dp-entry --aspect-type --quality-scan "ASSET=SCAN:HOURS" --dp-resource` |
| **WHY** | Records "as of now, a human vouches for this version." Everything downstream (check, wrapper) compares against what seal stored. |
| **WHO** | The STEWARD (human). Triggered manually today; in production triggered by an approval/certification event. |
| **KEY PARAMS** | `--dp-entry` = the DP entry name (for aspect writes; project NUMBER form). `--dp-resource` = the full search_entries name (for the semantic/lookup_context read). `--quality-scan ASSET=SCAN:HOURS` = maps a DQ scan + freshness SLA to an asset (hand-supplied in demo; discovery in production). `--aspect-type` = the verification aspect-type FQN. |
| **WRITES** | anchors[], source_tier=verified, verified_at, drift_summary=[], drifted_hash="", certified_text=<composed context>. |


---


## 3. `vcl.py check` — read-only drift detection


| Field | Detail |
|---|---|
| **WHAT** | Re-reads all 3 dimensions live, compares to the sealed anchors, prints per-anchor match/drift + verdict. Does NOT write anything. |
| **WHEN** | On a schedule (frequent, unattended) and any time a human wants to see current state. |
| **HOW** | `python3 vcl.py check` + same params as seal. |
| **WHY** | Answers "is the certification still valid?" without changing state. Safe to run anytime. |
| **WHO** | Scheduler (Cloud Run job) or a human checking. |
| **WRITES** | Nothing (read-only). |


---


## 4. `vcl.py enforce` — detect drift AND persist the verdict + pin


| Field | Detail |
|---|---|
| **WHAT** | Like check, but WRITES the result: flips `source_tier` to unverified on drift, writes `drift_summary` (which dimensions), and on SEMANTIC drift writes the atomicity pin (`drifted_hash` = current composed-context hash, `drift_detected_at`). |
| **WHEN** | On a schedule (the thing that actually moves a DP to `unverified` when it drifts). The wrapper reads what enforce wrote. |
| **HOW** | `python3 vcl.py enforce` + same params as seal. |
| **WHY** | Turns a detected drift into a persisted verdict the wrapper and triage can act on. The `drifted_hash` pin is the atomicity anchor: it records the EXACT version the drift verdict is about. |
| **WHO** | Scheduler (Cloud Run job), unattended. |
| **WRITES** | source_tier (verified/unverified), drift_summary=[...], and on semantic drift: drifted_hash, drift_detected_at. On verified/non-semantic: clears drifted_hash, removes drift_detected_at. |


---


## 5. `vcl_triage.py` — LLM advises steward: cosmetic vs substantive


| Field | Detail |
|---|---|
| **WHAT** | Compares OLD vs NEW business-rule text and classifies the change (cosmetic / substantive), names changed rules, recommends one-click-reapprove vs review-carefully. ADVISORY ONLY — never writes source_tier, never re-seals, never gates. |
| **WHEN** | After enforce records a semantic drift, when a steward is deciding whether the change is safe to re-approve. On-demand, human-triggered. |
| **HOW (gated, preferred)** | `python3 vcl_triage.py --dp-entry --dp-resource` — auto-fills OLD from stored `certified_text` and NEW from the pinned-verified current context. |
| **HOW (manual)** | `python3 vcl_triage.py --old "..." --new "..."` (or --old-file/--new-file) — for ad-hoc comparison. |
| **WHY** | Solves the "hash fires on a comma" problem: the deterministic hash catches EVERY change; the triage tells the human which changes are trivial (fast re-approve) vs dangerous (review). |
| **WHO** | The STEWARD (human), on-demand. Uses Vertex AI Gemini (needs roles/aiplatform.user). |
| **ATOMICITY GATE** | In --dp-entry/--dp-resource mode: reads `drifted_hash` pin, re-hashes current context, REFUSES if current != pin ("context changed again since drift detected; re-run enforce"). Guarantees the advice is about the exact version the verdict pinned. |
| **WRITES** | Nothing (advisory). |


---


## 6. `vcl_wrapper.py` — the runtime gate between agent and KC


| Field | Detail |
|---|---|
| **WHAT** | An MCP server that sits between an agent and Google's real KC MCP. Proxies everything unchanged EXCEPT `lookup_context`: for each requested Data Product it reads the stored verdict and either delivers the context (verified) or withholds it whole with an honest note (unverified). |
| **WHEN** | Every single agent request for grounding context. This is the ONLY component in the live request path. |
| **HOW** | Runs as a service: `export VCL_TOKEN=$(gcloud auth print-access-token); python3 vcl_wrapper.py` (listens on :8080/mcp). Agent points its MCP toolset at the wrapper instead of Google's endpoint. |
| **WHY** | Structural enforcement: withholds unverified context so an agent physically cannot ground on it. Whole-or-nothing per DP (never partial = never misleading). Names which dimension drifted so the steward knows what to re-certify. |
| **WHO** | The AGENT calls it (as its MCP tool source). It reads verdicts that enforce wrote. |
| **READS** | source_tier + drift_summary from the aspect (fast, no re-verify — the control/data-plane split: the wrapper NEVER runs verification, only reads what enforce persisted). |
| **CONFIG (env)** | VCL_TOKEN (bearer), VCL_PROJECT, VCL_LOCATION, VCL_ASPECT_TYPE, VCL_PORT. |
| **WRITES** | Nothing to the catalog (read-only verdict lookup). |


---


## Who-writes-what (the state ownership map)


| Aspect field | Written by | Read by |
|---|---|---|
| anchors[] | seal | check, enforce |
| source_tier | seal (verified), enforce (verified/unverified) | wrapper, triage (gate), check, enforce |
| drift_summary | enforce | wrapper (names drifted dim), triage (gate) |
| drifted_hash (pin) | enforce (semantic drift) | triage (atomicity gate) |
| drift_detected_at | enforce (semantic drift) | (audit) |
| certified_text | seal | triage (OLD baseline) |


## Trust / plane boundaries


- **vcl.py** = deterministic core, AI-FREE. Its SA: Dataplex + BigQuery read, aspect write. NO aiplatform.
- **vcl_triage.py** = advisory, AI-ALLOWED. Its SA: Dataplex read + roles/aiplatform.user (the ONLY component with model access).
- **vcl_wrapper.py** = runtime gate, READ-ONLY. Its SA: Dataplex read only. Most-exposed (internet-facing) = least privilege.
- **Control plane** (verify/write verdicts): seal, check, enforce — scheduled/manual, NOT in the request path.
- **Data plane** (act on stored verdicts): wrapper — every request, reads only, never re-verifies.


