# Governance drift review — substantive change

<!--
  Cloud Shell Tutorials walkthrough — steward workflow, SUBSTANTIVE branch. The drift
  watcher links THIS file when the advisory AI classification is "substantive":
    https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo=<PUBLIC_REPO>&cloudshell_tutorial=steward/walkthrough_substantive.md

  STRUCTURAL SAFETY: this file contains NO re-certify / seal command, by construction. A
  one-click re-certify of a weakened rule is therefore physically impossible from the
  substantive path — not merely "the backend promises not to."

  GENERIC (no per-drift substitution; safe for a PUBLIC repo). Which branch you are in IS
  the classification (this file = substantive). Drift details are shown natively on the
  console entry. No spotlight-pointer (devshell-activate-button doesn't exist while the
  walkthrough is already running inside Cloud Shell).
-->

## What drifted

A data product you own has **drifted** and is no longer verified. The Verified Context
Layer is currently **withholding** its governed context from agents until it is
re-certified — so this is safe, but it needs your review.

The Google Cloud console has opened on this data product's catalog **entry** alongside this
guide. On that entry, open the **Governance Drift** aspect to see which dimension drifted,
when, and the assistant's read. (That aspect is display-only — editing it certifies
nothing.)

## The AI triage verdict — substantive (advisory only)

You are on the **substantive** path: the assistant classified this change as
**substantive** — it may alter what an agent is permitted to do with the data (for example
a PII / exposure / calculation rule). The console's Governance Drift aspect shows the full
reasoning. This is advice only; it changes nothing on its own.

## Investigate before re-certifying

**Do not re-certify yet.** There is no one-click re-certify for a substantive change, and
this guide intentionally offers none.

Investigate first:

1. Confirm exactly which rule changed, and why, using the entry's rules/overview and the
   Governance Drift aspect in the console.
2. Check with the rule's owner that the new wording is intended and safe.
3. Only once the change is resolved should certification even be considered — and it is
   still done by re-running the deterministic verifier, never by editing a status field.

The data product stays **withheld (unverified)** until then — which is the safe state.

## Conclusion

No change was made to this data product's verification state; it remains withheld pending
your investigation. Re-certify only after the substantive change is resolved, by running
the deterministic verifier. You can close this tab.
