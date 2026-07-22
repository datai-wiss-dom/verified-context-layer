# Governance drift review — {{DP_DISPLAY_NAME}}

<!--
  Cloud Shell Tutorials walkthrough — steward workflow, SUBSTANTIVE branch.
  The backend targets THIS file's path in the deep link ONLY when the AI classification is
  "substantive":
    https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo={{GIT_REPO_URL}}&cloudshell_tutorial=steward/walkthrough_substantive.md

  STRUCTURAL SAFETY: this file contains NO seal / re-certify command, by construction. A
  one-click re-certify of a weakened rule is therefore physically impossible from the
  substantive path — not merely "the backend promises not to." A backend misroute degrades
  to a wrong-but-safe page, never a dangerous action.

  PARAMETERIZED TEMPLATE (backend fills {{PLACEHOLDER}} — no native Cloud Shell
  substitution). Placeholders: {{DP_DISPLAY_NAME}} {{DP_RESOURCE}} {{DRIFTED_DIMENSIONS}}
  {{DRIFT_DETECTED_AT}} {{AI_CLASSIFICATION}} {{AI_CHANGED_RULES}} {{AI_REASONING}}
  {{AI_RECOMMENDATION}}. Directives all documented; KC navigation is plain text; no real
  ids/emails.
-->

## What drifted

A data product you own has **drifted** and is no longer verified. The Verified Context
Layer is currently **withholding** its governed context from agents until it is
re-certified — so this is safe, but it needs your review.

- **Data product:** {{DP_DISPLAY_NAME}}
- **Resource:** `{{DP_RESOURCE}}`
- **Drifted dimension(s):** **{{DRIFTED_DIMENSIONS}}**
- **Detected:** {{DRIFT_DETECTED_AT}}

The Google Cloud console has opened on this data product's catalog entry alongside this
guide.

## The AI triage verdict (advisory only)

An assistant compared the **last-certified** rules against the **current** rules to help
you prioritize. **This is advice only — it is NOT a verdict and it changes nothing on its
own.** Only re-running the deterministic verifier can mark this data product verified
again; a human never edits the verdict directly.

- **Classification:** **{{AI_CLASSIFICATION}}**
- **What changed:** {{AI_CHANGED_RULES}}
- **Reasoning:** {{AI_REASONING}}
- **Recommendation:** {{AI_RECOMMENDATION}}

## Review the drift on the entry

In the console tab that opened on this entry:

1. Open the **Governance Drift** aspect to see the pending-review details (display-only —
   editing it does not certify anything).
2. Open the entry's **rules / overview** to see exactly what text changed.

## Investigate before re-certifying

The change is **substantive** — it may alter what an agent is permitted to do with the data
(for example a PII / exposure / calculation rule). **Do not re-certify yet.** There is no
one-click re-certify for a substantive change, and this page intentionally offers none.

Investigate first:

1. Confirm exactly which rule changed, and why, using the entry's rules/overview and the
   Governance Drift aspect.
2. Check with the rule's owner that the new wording is intended and safe.
3. Only once the change is resolved should certification even be considered — and it is
   still done by re-running the deterministic verifier, never by editing a status field.

The data product stays **withheld (unverified)** until then — which is the safe state.

## Conclusion

**{{DP_DISPLAY_NAME}}** remains withheld pending your investigation — no change was made to
its verification state. Re-certify only after the substantive change is resolved, by
running the verifier. You can close this tab.
