# PHASE SPEC / DESIGN — The Steward Workflow (native GCP Console)


> Read ARCHITECTURE.md and BUILD_GUIDELINES.md first; subordinate to both. This is the
> HUMAN half of VCL: how a data steward is notified of drift, reviews it with AI
> assistance, and re-certifies — entirely inside the Google Cloud Console, no custom app.


## The governing principle (non-negotiable)
**The human AUTHORIZES; the deterministic engine CERTIFIES.** The steward's "approve"
action triggers `vcl.py seal` (real re-fingerprinting of the live state), NEVER a
hand-flip of a status field. "Verified" always means "the fingerprints currently match,"
never "a human clicked a button." This extends ARCHITECTURE INV-2 (only vcl.py writes the
verdict) to the human: even the human doesn't write the verdict — they trigger the engine
that writes it. If a design step would let a steward set the verdict directly, it is
wrong (STOP, BUILD_GUIDELINES §0).


## Steward profile (drives every choice)
Semi/non-technical domain expert (data owner, governance lead). Lives in the GCP Console
+ email/chat. Never runs scripts unprompted. Acts on exception (push alerts), not by
  polling. Needs guidance, not a terminal.


---


## The journey (settled)


```
Drift → vcl.py enforce → verification aspect: source_tier = unverified
                       → backend writes a "Governance Drift" CUSTOM ASPECT on the DP:
                         { status: PENDING_REVIEW, drifted_dimensions, ai_classification,
                           ai_recommendation, drifted_at }  — DISPLAY ONLY (see below)
   ↓  (push)
Pub/Sub → email/chat alert with a DEEP LINK
   ↓
Deep link opens the GCP Console on the DP entry AND launches a Cloud Shell walkthrough
   ↓
Walkthrough (the "AI Assistant" sidebar):
   - shows: which DP, which dimension(s) drifted, the AI triage verdict + reasoning
   - SPOTLIGHTS the relevant Console UI (the entry / the custom aspect) so the steward
     sees the state natively
   - GATES the offered action on the AI classification:
       cosmetic    → offers a "copy to Cloud Shell" button for the RE-CERTIFY command
       substantive → does NOT offer re-certify; offers "Investigate" guidance only
   ↓
Steward clicks the button → the `vcl.py seal ...` command is copied into Cloud Shell →
   steward presses Enter → REAL deterministic re-verification runs
   ↓
seal updates the REAL verification aspect → source_tier = verified → wrapper delivers again
   ↓
audit record written to Firestore (SEPARATE store — the pull/dashboard/history surface)
```


## The two aspects — keep them straight (this is the crux)
- **`verification` aspect** — THE VERDICT. Written ONLY by vcl.py (seal/enforce). Read by
  the wrapper's gate. The steward NEVER edits it. The truth.
- **`Governance Drift` custom aspect** — DISPLAY ONLY. Written by the backend when drift is
  detected, to SHOW the steward (in the native entry UI) "this is pending review, here's
  the AI's read." The wrapper's gate MUST NOT read it. The steward MAY see it but editing
  it does NOT certify anything — certification only happens via seal.
- CHECK: `grep -nE "Governance.?Drift|custom.?aspect|PENDING_REVIEW" src/vcl_wrapper.py`
  returns NOTHING — the gate never reads the display aspect.


## Verified native mechanisms (confirmed 2026, docs.cloud.google.com/shell)
- **Deep link + walkthrough:** the "Open in Cloud Shell" link
  (`console.cloud.google.com/cloudshell/open?cloudshell_git_repo=...&cloudshell_tutorial=PATH.md`)
  clones a repo and opens a walkthrough markdown beside Cloud Shell.
- **Spotlight Console UI:** `<walkthrough-spotlight-pointer spotlightId=... | cssSelector=...>`
  highlights a Console element on click.
- **Copy command to shell:** walkthrough code blocks render a copy-to-Cloud-Shell button;
  the steward runs the real command with one click + Enter.
- LIMITATION (honest): the button COPIES the command; the steward presses Enter to run it.
  There is no silent background API call from the sidebar. For a demo this is GOOD — the
  steward visibly triggers the real seal. Production hardening (a real button → backend
  endpoint → seal) is future work, noted, not built here.


---


## What to build (demo scope — confirmed: not a production UI)


1. **The walkthrough** — a markdown file in the repo (`steward/walkthrough.md`) using the
   verified directives: intro (what drifted), the AI verdict display, spotlight the entry,
   and the AI-gated action (cosmetic → the seal command block; substantive → investigate
   guidance). Parameterize the DP so it's reusable.


2. **The "Governance Drift" custom aspect** — an aspect-type + the backend write that
   populates it on drift (PENDING_REVIEW + AI classification/recommendation). This is
   DISPLAY metadata. Terraform can create the aspect-TYPE (google_dataplex_aspect_type);
   the CONTENT is written by a small backend step (script/function), NOT Terraform
   (ARCHITECTURE §4).


3. **The push alert** — Pub/Sub topic + a notification (email/chat) carrying the deep
   link. Triggered when enforce marks a DP unverified. Terraform: the topic + subscription.
   The publish itself is a small step in/after enforce OR a separate watcher (decide and
   FLAG — see STOP triggers; do not silently modify vcl.py's enforce to publish, that
   touches the core — prefer a separate watcher that reads the verdict and publishes).


4. **The re-certify command** the button runs = the existing `vcl.py seal` with the DP's
   args. No new logic — the walkthrough just surfaces it.


5. **The audit record** — on re-certify, write to Firestore (the triage-audit phase, if
   built, already covers the store; here the steward decision is an additional event
   type). Keep SEPARATE from the verification aspect (INV-3).


## Non-goals / do NOT
- Do NOT build a custom React/standalone approval app (demo scope).
- Do NOT let the steward set the verdict by editing an aspect (governing principle).
- Do NOT let the wrapper gate read the Governance Drift display aspect (INV-5 reads only
  `verification`).
- Do NOT modify vcl.py's seal/enforce LOGIC. The walkthrough surfaces seal; the watcher
  reads the verdict. If publishing an alert seems to require editing enforce, STOP and
  propose the separate-watcher approach instead.
- Do NOT build the discovery/graph plane.


## Steps (each followed by a round-trip read — BUILD_GUIDELINES §1)
1. VERIFY the walkthrough directives + deep-link format against current docs (they were
   confirmed 2026, but re-confirm the exact directive syntax before authoring). Show it.
2. Author `steward/walkthrough.md` (parameterized). Test it opens via the deep link and
   spotlights correctly — paste what you observed.
3. Governance-Drift aspect-type (Terraform) + the backend write step. Apply, then READ
   BACK the aspect content on a drifted DP and paste it.
4. Pub/Sub topic + subscription (Terraform) + the separate watcher that publishes the
   alert with the deep link on unverified. Trigger a drift, confirm the alert fires with a
   working deep link — paste it.
5. END-TO-END: drift a DP → alert arrives → deep link opens Console + walkthrough →
   walkthrough shows AI verdict + gates the action → (cosmetic) run the seal command →
   verified → wrapper delivers again → audit recorded. PASTE the observed chain.


## Invariant checks to paste at the end (ARCHITECTURE §1 + this spec)
- `grep -nE "genai|vertexai" src/vcl.py` → nothing (INV-1).
- wrapper/vcl.py unchanged in verdict logic (INV-2, INV-3).
- wrapper does NOT read the Governance Drift display aspect (grep above).
- the steward's approve triggered `seal` (show the command that ran), NOT a status edit.


## STOP triggers (BUILD_GUIDELINES §0)
- If alerting seems to need editing vcl.py's enforce → STOP, propose a separate watcher.
- If the walkthrough can't gate the action on the AI verdict cleanly → STOP and report;
  do NOT offer one-click re-certify for substantive drift under any circumstance.
- If any step would let the steward certify without running seal → STOP; that violates
  the governing principle.


## Report shape: BUILD_GUIDELINES §7.
