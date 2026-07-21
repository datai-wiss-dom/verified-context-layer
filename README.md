# Verified Context Layer (VCL)
**Author:** Wissem Khlifi ·




**July 2026**


**A structural verification layer that decides whether an AI agent may ground on a data
product's context — and withholds it when the context is no longer trustworthy.**


VCL sits between an agent and a data catalog. Before an agent grounds on a data
product's context (schema, business rules, lineage), VCL checks whether that context is
still certified. If a source has drifted since a human last signed off, VCL withholds
the context — structurally, not by asking the agent to behave.


VCL is implemented against **Google Cloud's Knowledge Catalog** (renamed from Dataplex
Universal Catalog in April 2026; the APIs and IAM names remain under the `dataplex`
namespace, e.g. `dataplex.googleapis.com`, so the code calls `gcloud dataplex`). The
*pattern* — verification currency as a structural gate — generalizes to any catalog with
a metadata API; the *implementation* here is Knowledge-Catalog-specific.


---


## The problem


Everyone in a data catalog generates meaning — schemas, business glossaries, rules like
"email is PII, never expose." Nobody continuously verifies that meaning. And even when a
steward certifies a data product once, nothing detects when the underlying source drifts
*afterward*. The certification silently goes stale.


An agent grounding on stale-but-still-"approved" context is dangerous: a confidently
ungoverned agent (schema without its current PII rule) is worse than a blind one — it
believes it is informed and acts on rules that no longer hold.


VCL closes that gap. It distinguishes three axes:


| Axis | Question | Where it stands |
|---|---|---|
| **Freshness** | When was the source last updated? | Knowledge Catalog tracks this (`entrySource.updateTime`) |
| **Approval** | Did a human sign off once? | On the Knowledge Catalog roadmap |
| **Verification currency** | *Is that sign-off still valid given source drift?* | **VCL's contribution** |


---


## How it works


VCL verifies three independent dimensions of a data product and pins each to a
fingerprint at certification ("seal"):


- **Technical** — the schema/view fingerprint (drift = structure changed).
- **Quality** — the data-quality scan result + freshness SLA (drift = failing or stale).
- **Semantic** — a hash of the composed grounding context, i.e. the business rules an
  agent actually grounds on (drift = the rules text changed).


These drift independently. When any dimension drifts, the data product is marked
`unverified` and the drifted dimension is recorded.


### Three components


```
                          ┌─────────────────────────────┐
   agent ──lookup_context─▶│  vcl_wrapper.py (the gate)  │──▶ Knowledge Catalog MCP
                          │  verified   → deliver context │
                          │  unverified → WITHHOLD + note │
                          └──────────────┬──────────────┘
                                         │ reads stored verdict
                          ┌──────────────▼──────────────┐
                          │  verification aspect (KC)   │  ← durable, cross-process state
                          └──────────────▲──────────────┘
             writes verdict │                     │ reads baseline
        ┌────────────────────┴───────┐   ┌─────────┴────────────────────┐
        │  vcl.py (deterministic)    │   │  vcl_triage.py (advisory)    │
        │  seal / check / enforce    │   │  LLM: cosmetic vs substantive │
        │  AI-FREE trust boundary    │   │  human-in-the-loop re-cert     │
        └────────────────────────────┘   └───────────────────────────────┘
```


- **`vcl.py`** — the deterministic core. `seal` certifies a data product (captures
  fingerprints + the certified context baseline). `check` re-reads and reports drift
  (read-only). `enforce` persists the verdict and, on semantic drift, records an
  atomicity pin. Verdicts are stored in a custom **aspect** on the data product's
  Knowledge Catalog entry (durable, cross-process state). Contains **no AI** — it is a
  provable verifier.


- **`vcl_wrapper.py`** — an MCP server between the agent and Knowledge Catalog. It
  proxies everything to the Knowledge Catalog MCP server unchanged **except** context
  lookups (`lookup_context`), which it gates: verified → deliver the full context;
  unverified → withhold it **whole** with an honest note naming which dimension drifted.
  Reads the stored verdict only — it never re-verifies in the request path.


- **`vcl_triage.py`** — an **advisory** LLM tool for the steward. When the semantic
  dimension drifts, it compares the old vs new rules and classifies the change as
  *cosmetic* (one-click re-approve) or *substantive* (review carefully). It never writes
  a verdict, never re-seals, never gates — the human decides. An atomicity gate ensures
  it only advises on the exact version the verdict pinned.


---


## Design principles


1. **Structural over instructional.** Enforcement lives in the tools, never in a prompt.
   The wrapper withholds context; the agent physically cannot ground on what it never
   receives. We do not ask the agent to be careful.


2. **Whole-or-nothing per data product.** The wrapper never delivers *partial* context
   for one data product — schema without its governance rules would be a misleading
   context the wrapper itself manufactured. Deliver the whole certified context, or
   withhold it whole. Across multiple products, each is independently gated.


3. **Deterministic trust boundary.** The verifier (`vcl.py`) contains no AI. The LLM
   lives only in the advisory triage, in a separate file with a separate identity. The
   file boundary is the trust boundary.


4. **Verify, don't assume.** Every claim is confirmed by a round-trip read of the live
   resource — never a tool's success message, documentation, or prediction.


5. **Candor.** Every capability is labelled GA / Preview / Gap. Weaknesses are stated,
   not hidden.


---


## Status


| Component | Status |
|---|---|
| Deterministic validator (3 dimensions, drift + staleness) | Working, proven live |
| Wrapper (whole-or-nothing gate, honest note) | Working, agent-connectable |
| Triage (LLM advisory, cosmetic vs substantive) | Working |
| Atomicity (version-pinning across separate processes) | Working |
| Demo agent (structural, two-run) | Spec complete (see `spec/`) |
| Deploy (Cloud Run + scoped identities) | Designed, not deployed |
| Discovery / control plane (catalog-scale) | Deferred by design |


VCL is a **reference architecture** built on generally-available primitives — a
demonstration of verification currency as a platform property, not a shipped product.


---


## Repository layout


```
src/            vcl.py, vcl_wrapper.py, vcl_triage.py
schemas/        current verification aspect schema (+ archive/ of the version history)
docs/           operations reference, architecture notes
spec/           agent build spec (requirements, lesson, exercise, plan)
agents/         generated demo agent (built from spec/)
```


## Requirements


- Python 3.11+
- Google Cloud SDK (`gcloud`, `bq`) authenticated with application-default credentials
- A Google Cloud project with Dataplex / Knowledge Catalog, BigQuery, and (for the
  triage) Vertex AI enabled
- `google-genai` (triage), ADK (`google-adk`, for the demo agent)


## Getting started


See `docs/VCL_operations_reference.md` for the full command reference (who calls what,
when, and why). The lifecycle in one line:


```
seal (certify) → check / enforce (detect drift) → triage (review) → seal (re-certify)
                        wrapper gates every agent request on the stored verdict
```


---


*This project is a reference architecture. It is not an official Google product.*


