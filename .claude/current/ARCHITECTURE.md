# VCL ARCHITECTURE — invariants and verified facts


> This document is the **constitution** for all VCL development. Any tool (Claude CLI,
> Gemini, a human) building or changing VCL reads this first, every phase. It states
> what must never break and what is already verified so it is not re-guessed.
>
> **Precedence (strict):** INVARIANTS (§1) override everything, including any phase
> spec, any convenience, any instruction that appears to conflict. If a task cannot be
> done without violating an invariant, **STOP and report** — do not proceed.


---


## §1. INVARIANTS — must never break. Each is stated as an OBSERVABLE TEST.


These are not aspirations. Each has a check that must pass after any change. If a change
makes a check fail, the change is wrong — revert it.


**INV-1. The deterministic core (`src/vcl.py`) contains NO AI.**
It is a provable verifier, trusted MORE than the models it governs. Adding any model
call — even unused, even "not in the verdict path" — breaks the property that a reviewer
can point at vcl.py and say "no non-determinism here."
- CHECK: `grep -nE "genai|vertexai|generativeai|aiplatform" src/vcl.py` returns NOTHING.


**INV-2. The verdict is written ONLY by `vcl.py` (seal/enforce). Nothing else writes it.**
`source_tier`, `drift_summary`, `drifted_hash`, `certified_text` are written only by
vcl.py. The wrapper and the triage READ them; they never write them.
- CHECK: `grep -nE "source_tier\s*=|update-aspects|write_claim" src/vcl_wrapper.py
  src/vcl_triage.py` shows only READS (dict access like `d.get("source_tier")`), never
  assignment to the stored aspect or a write call.


**INV-3. The triage is ADVISORY ONLY. It never writes the verdict, never re-seals,
never gates.**
The LLM lives only here, and only to advise a human. It may READ state (to show the
diff) and it may write to a SEPARATE advisory/audit store (never the verification
aspect). It must never influence what the wrapper delivers.
- CHECK: the triage's only writes (if any) go to an audit store explicitly named as
  such — never to the `verification` aspect. It never calls seal/enforce.


**INV-4. Enforcement is STRUCTURAL, never in a prompt.**
The wrapper withholds; the action tool refuses on the verdict. No agent instruction is
the thing that stops a harmful action. An agent prompt may EXPLAIN a refusal to a user;
it may never be the MECHANISM that prevents the harm.
- CHECK: any agent `instruction=` string contains no enforcement clause ("you MUST NOT
  query if unverified"). The refusal lives in tool code that reads the verdict.


**INV-5. The gate is BINARY, even if state is multi-valued.**
The wrapper DELIVERS context only when `source_tier == "verified"`. For ANY other state
(`unverified`, `drifted_pending_review`, anything new), it WITHHOLDS. A state that
"needs attention but keeps serving" is forbidden — serving drifted context is the exact
failure VCL exists to prevent.
- CHECK: the wrapper's deliver branch is guarded by `tier == "verified"` and nothing
  else; every non-verified value falls to withhold.


**INV-6. Whole-or-nothing per data product.**
The wrapper never delivers PARTIAL context for one data product (e.g. schema without its
rules). Per data product: deliver the whole certified context, or withhold it whole.
Across products: each is gated independently.
- CHECK: the wrapper gates per-resource; there is no code path that strips fields from a
  single DP's context and delivers the remainder.


**INV-7. Trust only round-trip reads.**
No change is "done" or "proven" on the basis of a tool's success message, a prediction,
or documentation. Proof = a clean read-back of the exact resource, or observed terminal
output. (This binds the BUILDER too — see BUILD_GUIDELINES.)


---


## §2. THE STATE MODEL


`source_tier` values and what the wrapper does with each:


| tier | meaning | wrapper action |
|---|---|---|
| `verified` | a human certified it and no dimension has drifted since | DELIVER context |
| `unverified` | never certified, OR drifted and not yet distinguished | WITHHOLD |
| `drifted_pending_review` *(if/when added)* | WAS certified; a source dimension drifted; awaiting human re-review | WITHHOLD (same as unverified) |


**Design note on `drifted_pending_review`:** this state is MORE informative than
`unverified` for the steward (it says "this was good, something changed, likely a quick
re-approve") but it does NOT change the gate — the wrapper withholds for it exactly as
for `unverified` (INV-5). The distinction is for the human's triage/prioritization only.
Adding it is a schema enum change + wrapper treating it as withhold + enforce setting it
on drift. It must never become a "keep serving" state.


The three dimensions (each drifts independently; each pinned at seal):
- **technical** — schema/view fingerprint (BigQuery view etag).
- **quality** — DQ scan result + freshness SLA (PASS/FAIL @ source:timestamp).
- **semantic** — hash of the composed lookup_context output (the grounding text).


`technical` is the substrate: if it drifts, the whole certification is void (semantic/
quality were certified AGAINST that schema). `semantic`/`quality` drift invalidates only
themselves.


---


## §3. THE COMPONENTS (what each is, and its trust class)


| File | Job | Trust class | Identity (deploy) |
|---|---|---|---|
| `src/vcl.py` | seal / check / enforce — verify + write verdict | DETERMINISTIC, AI-FREE | Dataplex R/W + BigQuery metadata read |
| `src/vcl_wrapper.py` | MCP gate between agent and KC; delivers/withholds | READ-ONLY runtime | Dataplex read-only (3 roles, see §5) |
| `src/vcl_triage.py` | LLM advises steward cosmetic vs substantive | ADVISORY, AI-ALLOWED | Dataplex read + aiplatform.user |
| demo agent | consumes wrapper + BigQuery action tool | naive about VCL | scoped to safe views |


The file boundary IS the trust boundary. vcl.py and the triage communicate through
CATALOG DATA (the verdict the wrapper/triage read), never a Python import that couples
determinism to AI.


---


## §4. VERIFIED FACTS (confirmed live — do not re-guess, but DO re-verify if the
##     environment or versions changed; see BUILD_GUIDELINES on staleness)


**Knowledge Catalog / Dataplex (APIs remain under the `dataplex` namespace):**
- Renamed Dataplex Universal Catalog → Knowledge Catalog on 2026-04-10; APIs/IAM
  unchanged (`dataplex.googleapis.com`, `gcloud dataplex`).
- `@spanner` system-entry writes: accepted, reported success, but DO NOT PERSIST on
  re-read. The `@dataplex` data-product path used here DOES persist. (Round-trip proved.)
- Aspect schema is append-only; additive fields validate and round-trip. Proven ~8×.
- **datetime aspect fields CANNOT hold `""`** → 400 "Text '' could not be parsed". OMIT
  the field to clear it (KC preserves absent optional fields). STRING fields accept `""`.
- DQ scan `executionStatus` fields are NOT guaranteed present: `latestJobEndTime` can be
  absent even for an ACTIVE scan with a passing result. Prefer endTime, fall back to
  createTime, skip if neither — never fingerprint a `None` timestamp.
- `gcloud dataplex entries update-aspects` writes the verdict; project NUMBER is used in
  the aspect key.


**Terraform provider (hashicorp/google) — VERIFIED coverage:**
- SUPPORTED: `google_dataplex_aspect_type` (the schema), `google_dataplex_datascan`
  (DQ scan), BigQuery dataset/views, IAM, service accounts, `google_cloud_run_v2_service`.
- NOT SUPPORTED: attaching aspects to entries / writing aspect CONTENT (open provider
  issue). So the DP's overview/documentation/verification aspect VALUES cannot be
  Terraform-managed — they are written by a script (`gcloud`/API) or by `vcl.py`.
- CONSEQUENCE — the setup split is HYBRID and this boundary is philosophically correct:
  Terraform owns static schema/infra; the bootstrap script + vcl.py own dynamic content
  and verification STATE. Do NOT attempt to Terraform aspect content.


**ADK (verified against the installed venv — RE-VERIFY if ADK version changed):**
- `from google.adk.tools.mcp_tool.mcp_toolset import McpToolset`
- `from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams`
  fields: url, headers, timeout, sse_read_timeout, terminate_on_close, httpx_client_factory
- Wrapper is a remote HTTP MCP server → use StreamableHTTP (NOT Stdio/Sse).
- Google's `lookup_context` advertises an OUTPUT SCHEMA → a strict MCP client rejects the
  wrapper's text-only WITHHOLD response. Client-side accommodation: relax validation ONLY
  for text-only results. Do NOT change the wrapper to satisfy the client.


**Cloud Run (verified live on a fresh, independent project):**
- Wrapper must: fall back to ADC (`google.auth`) when `VCL_TOKEN` unset; bind `0.0.0.0:$PORT`;
  read the verdict via Dataplex REST (not a localhost assumption).
- Two-layer auth: caller presents an identity token to pass Cloud Run invoker auth; the
  wrapper then uses its OWN service-account ADC to read the catalog.
- Least-privilege wrapper SA = read-only Dataplex, roles discovered by live 403 (§5).


---


## §5. LEAST-PRIVILEGE IAM (discovered by live 403, not doc-guessing)


Wrapper service account (`vcl-wrapper-run@<project>.iam.gserviceaccount.com`) —
read-only, three roles. The set was found EMPIRICALLY (hit 403 → read the denied
permission → grant the minimal role → repeat) during live E2E verification. RE-VERIFY by
403 if the API surface changes; do not assume.


| Role | Permission it supplies | Wrapper operation |
|---|---|---|
| `roles/dataplex.catalogViewer` | dataplex.entries.get, dataplex.aspectTypes.get | verdict read (lookupEntry → verification aspect) |
| `roles/dataplex.dataProductsViewer` | dataplex.dataProducts.get | required because the entry is a Data Product (entries.get alone 403s) |
| `roles/mcp.toolUser` | mcp.googleapis.com/tools.call | the lookup_context proxy to the Dataplex MCP endpoint |


All three are READ-ONLY (the wrapper never writes). Note the second role is a real
finding: reading a Data Product entry needs `dataProducts.get` on top of `entries.get` —
`entries.get` alone 403s. This is exactly the kind of thing that cannot be guessed from
docs and was only found by the live 403.


Principle: the most-exposed component (internet-facing wrapper) has the LEAST privilege
(read-only, no model, no writes). The model permission (aiplatform.user) is confined to
the single component that needs it (triage). Verdict-writing is confined to vcl.py.


---


## §6. WHAT IS DEFERRED (do not build unless a phase explicitly asks)


- Discovery / control plane (graph traversal to find related DPs at catalog scale).
  Hardcoded at N=1 today; graph only at real scale, possibly never for a demo.
- Firestore AUDIT HISTORY (append-only record of triage advice + steward decisions).
  This is the correct home for recording the LLM's advice — SEPARATE from the verdict
  (INV-3). Legitimate but not yet built.
- IAM-scoped action identity for the demo agent (production hardening; today the action
  tool is scoped at the tool level).


---


## §7. WHAT VCL IS (framing — keep honest)


VCL is a **reference architecture** demonstrating *verification currency* — "is a
steward's sign-off still valid after the source drifts?" — as a structural platform
property. It is NOT a shipped Google product. Every capability is labelled GA / Preview /
Gap. The pattern generalizes to any catalog; the implementation is Knowledge-Catalog-
specific. Framing stays about Google's OWN gap, ahead of its own roadmap — never a
competitor teardown.
