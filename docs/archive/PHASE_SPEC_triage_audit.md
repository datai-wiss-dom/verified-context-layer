# PHASE SPEC — Triage Audit Recording


> Read ARCHITECTURE.md and BUILD_GUIDELINES.md first; this spec is subordinate to both.
> This is a SAFE, ADDITIVE phase: it records the triage's advice to a separate audit
> store. It must not touch the verdict path or the proven gate.


## Goal
When `vcl_triage.py` advises a steward (cosmetic vs substantive), also WRITE that advice
to an append-only audit store, so there is a durable record of: what drifted, when, which
version, what the LLM advised, and that it was advisory. The steward (and future
auditors) can then see the history of drift → advice → (their) decision.


## The single most important constraint (ARCHITECTURE INV-3)
The triage is ADVISORY ONLY. This audit record:
- goes to a SEPARATE store (Firestore), NEVER the `verification` aspect.
- is NEVER read by the wrapper's gate or by vcl.py's verdict logic.
- must not create any path by which the LLM's advice influences what the wrapper
  delivers. It is a human-facing log, full stop.
- CHECK after building: `grep -nE "firestore|datastore|audit" src/vcl.py
  src/vcl_wrapper.py` returns NOTHING. Only the triage writes audit; only humans read it.


## Non-goals (do NOT do)
- Do NOT change vcl.py or vcl_wrapper.py at all (INV-1, INV-2, INV-3).
- Do NOT change the verdict, the gate, the schema, or the triage's ADVICE logic.
- Do NOT let the audit write block or alter the advice output (see best-effort below).


---


## What the audit record must contain
Enough that the record is meaningful and trustworthy WITHOUT re-running anything:
- `dp_resource` — which data product.
- `recorded_at` — timestamp of the triage run.
- `drifted_hash` — the version pin the advice is about (from the verdict the triage read;
  ties the advice to the exact version — ARCHITECTURE atomicity). If gate mode wasn't
  used and there's no pin, record null and note it.
- `drift_summary` — which dimension(s) drifted (e.g. ["semantic"]).
- `classification` — cosmetic | substantive (the LLM's output).
- `changed_rules`, `reasoning`, `recommendation` — the LLM's advice, verbatim.
- `model` — the model id used (e.g. gemini-2.5-flash) and `advisory: true`, so a reader
  never mistakes this for a verdict.
- `certified_text_hash` / `current_text_hash` — the old/new fingerprints compared (not
  necessarily the full text; hashes are enough for the audit trail and avoid storing
  large text — but capturing the diff summary is fine).
  NOTE: this record is ADVICE + PROVENANCE, never a decision. If/when a steward's
  re-certification is recorded, that is a SEPARATE event (a future enhancement), not this.


## Store: Firestore (Native mode)
- Collection e.g. `vcl_triage_audit`, one document per triage run (auto-id).
- Append-only in spirit: the triage only CREATES documents; it never updates/deletes.
- Why Firestore and not the aspect: it is a DIFFERENT system, so an audit write
  structurally cannot leak into the deterministic gate (INV-3 by construction). It is
  also the right shape for append-only per-DP history (ARCHITECTURE §6).


## Best-effort (must never block the advice)
The triage's PRIMARY job is to advise the human. The audit write is secondary:
- Wrap the Firestore write in try/except. On failure, PRINT a clear "[audit write failed:
  ...]" line and STILL print the advice and exit normally.
- The steward must always get the advice even if Firestore is unavailable.


---


## IAM (state it explicitly — this expands the triage SA slightly)
The triage SA currently has: Dataplex read + roles/aiplatform.user.
This phase adds: `roles/datastore.user` (Firestore read/write) to the TRIAGE SA ONLY.
- Do NOT add Firestore permissions to the wrapper SA or the vcl.py/validator SA — they
  must not touch the audit store (INV-3).
- VERIFY the exact role by the live-403 method if unsure (BUILD_GUIDELINES §2), do not
  assume the role name.


## Terraform (the only infra in this phase)
- `google_firestore_database` (Native mode) if the project has none — VERIFY the resource
    + that only one default database is allowed per project in the installed provider
      before writing (BUILD_GUIDELINES §2).
- The `roles/datastore.user` binding on the triage SA (variables/tfvars, gitignored,
  leak-clean — BUILD_GUIDELINES §6).
- No other infra. (The state change and gate are untouched — this phase adds a store and
  one role, nothing else.)


---


## Steps
1. VERIFY (BUILD_GUIDELINES §2): the Firestore Python client is installed (or add it via
   uv, per §6 no-hardcoded-secrets); the Terraform Firestore resource + datastore.user
   role exist in the installed provider. Show the checks.
2. Terraform: Firestore database + triage-SA datastore.user binding. Apply, then READ
   BACK (describe the database, show the binding) — not "apply complete" (§1).
3. `src/vcl_triage.py`: after producing the advice (unchanged), write the audit record,
   best-effort. Do not alter the advice logic or output; only ADD the write + a status
   line.
4. RUN it end to end on the working project against a real drift:
   seal → drift → enforce → triage (gate mode) → confirm it (a) still prints the same
   advice AND (b) wrote a Firestore document. READ THE DOCUMENT BACK and paste it (§1) —
   a tool "success" is not proof; the round-tripped document is.
5. Prove best-effort: simulate/observe an audit-write failure path (or reason about it in
   code) and confirm the advice still prints. State how you verified this.


## STOP triggers (BUILD_GUIDELINES §0)
- If adding the audit write requires changing the triage's ADVICE logic or output — STOP;
  it should be purely additive.
- If the Firestore write can't be made best-effort cleanly — STOP and report.
- If you find yourself needing to touch vcl.py or vcl_wrapper.py — STOP; this phase must
  not touch them (INV-3 check will fail otherwise).


## Report shape (BUILD_GUIDELINES §7)
Changed files · Authored/Ran/Verified with output · Decisions flagged · Not-done/needs-
human · Invariant checks (paste the INV-3 grep result showing vcl.py/wrapper untouched by
audit code, and the round-tripped Firestore document).
