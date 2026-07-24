# VCL Control Plane — Design

> **Status: SPECIFIED, NOT BUILT.** This is a design specification only. No control-plane
> code, Terraform, or scaffolding exists, and none should be created from this document.
> VCL today runs at **N = 1** (one data product); the control plane is the layer that would
> be needed at catalog scale. Building it is a separate, explicitly-scoped decision — it is
> **not** implied by the existence of this file.

---

## §1. The problem — fan-out

Today VCL is deliberately **per–data-product and per-anchor**:

- `vcl.py enforce` runs against one DP, re-fingerprints that DP's anchors, and writes that
  DP's verdict (`verification.source_tier`).
- It emits **one** `VCL_DRIFT_DETECTED` log entry **per diverged anchor**.
- The wrapper gates **per DP**, on that DP's verdict only.

At N = 1 this is complete and correct. At catalog scale it is not, because of **fan-out**:
a **single source change** can invalidate anchors across **many** data products at once.

Concrete example: the base table `ecommerce.customers` gains or retypes a column. Every data
product whose **technical** anchor fingerprints a view over `customers` drifts at the same
moment. One root cause → *N* diverged anchors → *N* DPs → *N* alerts.

**The gap this exposes:** there is **no single resolution path** for that fan-out. A steward
receives *N* independent alerts, opens *N* entries, and re-certifies *N* DPs — with nothing
telling them these drifts are the *same event*, and re-certifying one telling the others
nothing. The per-anchor design is right *locally* but has no notion of *"these drifts are one
root cause."* The control plane is the layer that supplies that notion.

## §2. Goals and non-goals

**Goals**
1. **Discovery** — given a changed source, find the data products that depend on it.
2. **Correlation** — group simultaneous drifts that share a root cause into one *drift group*.
3. **Group resolution** — present **one** review/re-cert path per group, not *N*.
4. **Group-level alerting** — one alert per root-cause event, not *N* per-anchor alerts.

**Non-goals (hard boundaries — must not break existing invariants)**
- It must **not** change the deterministic core. `vcl.py` (seal/check/enforce) stays per-DP,
  per-anchor, AI-free, with **no cross-DP awareness** (INV-1). The gate stays binary and per-DP
  (INV-5).
- It must **not** become a new gate or a new source of truth. The verdict remains the
  `verification` aspect written **only** by `vcl.py` (INV-2). The control plane **correlates and
  routes**; it never certifies.
- It must **not** auto-resolve. A group re-cert still bottoms out on the human authorizing and
  the deterministic engine re-fingerprinting **each** DP.

## §3. Where it sits

A layer **above** the per-DP core, not inside it. The core stays local and deterministic; the
control plane **consumes what the core already emits** (the `verification` aspects + the
per-anchor drift events) and adds discovery, correlation, and group routing on top.

It is **read-mostly** over the catalog and the drift-event stream. Its only writes are its own
correlation/group records, which live in a **separate store** (the same discipline as the
advisory audit store) — **never** the verdict.

## §4. The model — the dependency graph

- **Nodes:** sources (BigQuery tables/views, DQ scans, rule text), anchors
  (technical/quality/semantic), and data products.
- **Edges:** an anchor is `measured_against` a source; a DP declares its anchors; sources depend
  on sources (a view over a table).
- A source change **propagates along edges** to the set of anchors (and thus DPs) whose
  fingerprints were computed against it.

**Discovery** = traverse this graph from a changed source to its dependent DPs. Two data sources
already exist for it, and this design would reconcile them (see §7 OQ3):
- **Dataplex / Knowledge Catalog lineage** (`datalineage.googleapis.com`, already enabled in
  `setup/`) — the catalog-scale view, but potentially incomplete or lagging.
- **The anchors' own `measured_against` fields** — exact, because each records the precise source
  a fingerprint was read from, but only for sources that have already been sealed.

## §5. Components (all UNBUILT — described, not scaffolded)

- **a. Discovery / traversal.** Given a changed source, enumerate the dependent DPs via lineage
  plus `measured_against`.
- **b. Correlation stage.** Group per-anchor drift events that trace to one root-cause source
  change into a single drift group within a time window, and assign a correlation id. It
  **consumes** the per-anchor `VCL_DRIFT_DETECTED` events; it does not produce verdicts.
- **c. Group resolution.** One review path per group: a group **SEE** (all affected entries) and
  a **coordinated re-cert**. The re-cert still runs per-DP `vcl.py seal` underneath — the engine
  re-fingerprints each DP; the control plane only sequences and tracks the set.
- **d. Group-level alerting.** One alert per drift group (per root-cause event), carrying the
  group, instead of *N* per-anchor alerts. Origin of this alert is the subject of §7 OQ1.

## §6. Integration with existing work

- **Reuses, changes nothing in the core:** the `verification` aspects (per-DP truth), the anchors'
  `measured_against`, the per-anchor `VCL_DRIFT_DETECTED` log stream, and the already-enabled
  `datalineage` API.
- The correlation stage **consumes the drift events `enforce` already emits** — it does not
  require `enforce` to change. `enforce` keeps emitting per-anchor; correlation groups them
  downstream.
- A group re-cert still bottoms out on per-DP `vcl.py seal`. The provenance fields already added
  (`sealed_by` / `seal_event_id`) support it directly: a coordinated re-cert can share **one
  `seal_event_id` across the group**, giving a traceable *"these DPs were re-certified as one
  event."* No schema change is required for that.

## §7. Open questions

1. **Where does group-level alerting originate?**
   Today `enforce` emits `VCL_DRIFT_DETECTED` **per anchor**, and the Monitoring policy alerts
   **per matching log line** — i.e., per anchor. Group-level alerting **cannot** come from
   `enforce`: `enforce` is per-DP and deterministically local, and giving it cross-DP awareness to
   emit group alerts would break that locality/determinism (INV-1). Therefore group alerting must
   originate from a **separate correlation stage** that consumes the per-anchor events and emits
   one group alert.
   **Implication for existing work:** the current alerting path
   (`enforce` → `logs/vcl-drift` → Monitoring policy → Slack/email) is inherently **per-anchor**.
   A control plane would insert a correlation stage **between** the per-anchor events and the
   alert; the group alert is emitted from **that stage**, not from `enforce` and not from a
   per-log-line Monitoring policy.

2. **Correlation identity and window.** How is "same root cause" decided — same `measured_against`
   source? A shared lineage ancestor? Within what time window? This trades off over-grouping
   (hiding a genuinely separate drift) against under-grouping (the fan-out problem returning).

3. **Discovery authority: lineage vs `measured_against`.** Lineage is catalog-wide but may lag or
   be incomplete; `measured_against` is exact but only for already-sealed anchors. Which is
   authoritative when they disagree?

4. **Group resolution semantics.** A group can be **partially** resolved (some DPs re-certified,
   others not). Does a group stay "open" until all members resolve, and how does that coexist with
   the **binary, independent per-DP gate** — each DP still delivers or withholds on its own verdict
   regardless of group state?

5. **Scale, state, and cost.** Where does correlation state live (a separate store, like the audit
   DB), and what is the cost of traversal + correlation at catalog scale?

---

*This document is a design artifact. It specifies; it does not build. Any implementation is a
separate, explicitly-authorized task.*
