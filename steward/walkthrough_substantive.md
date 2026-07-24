# Governance drift review
**Author:** Wissem Khlifi · July 2026

<!--
  Cloud Shell Tutorials walkthrough — steward workflow. This is the DEFAULT landing for
  EVERY governance-drift alert: the Monitoring policy's deep link targets THIS file, which
  by construction contains NO re-certify command. The steward reads the AI assessment on the
  Knowledge Catalog entry and branches:
    - substantive -> investigate here (nothing is re-certified; stays withheld — the safe state)
    - cosmetic    -> follow the onward LINK to steward/walkthrough_cosmetic.md, which holds
                     the re-certify command.
  STRUCTURAL SAFETY: the re-certify command is reachable ONLY by first passing through this
  file, which requires reading the classification. The onward step is a LINK, not a command,
  so a substantive change has no one-click re-certify path by CONSTRUCTION — not by a warning.
  Deep link form (the alert now targets THIS file):
    https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo=<PUBLIC_REPO>&cloudshell_tutorial=steward/walkthrough_substantive.md
-->

## What drifted

A data product you own has **drifted** and is no longer verified. The Verified Context
Layer is currently **withholding** its governed context from agents until it is
re-certified — so this is safe, but it needs your review.

The Google Cloud console has opened on this data product's catalog **entry** alongside this
guide. On that entry, open the **Governance Drift** aspect to see which dimension drifted,
when, and the assistant's read. (That aspect is display-only — editing it certifies
nothing.)

## Read the assessment, then choose your path

The entry's **Governance Drift** aspect shows the assistant's advisory assessment —
**cosmetic** or **substantive** — with its reasoning. This is advice only; it changes
nothing on its own. Your next step depends on which it is.

## If the assessment is SUBSTANTIVE — investigate (do not re-certify)

A substantive change may alter what an agent is permitted to do with the data (for example a
PII / exposure / calculation rule). **There is no one-click re-certify here, and this guide
intentionally offers none.** Investigate first:

1. Confirm exactly which rule changed, and why, using the entry's rules/overview and the
   Governance Drift aspect in the console.
2. Check with the rule's owner that the new wording is intended and safe.
3. Only once the change is resolved should certification even be considered — and it is still
   done by re-running the deterministic verifier, never by editing a status field.

The data product stays **withheld (unverified)** until then — which is the safe state.

## If the assessment is COSMETIC — re-certify

A cosmetic change leaves the meaning of the rules unchanged, so it can be re-certified. The
re-certify command lives in a **separate** walkthrough — open it here:

**→ [Re-certify: open the cosmetic walkthrough](https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo=https://github.com/datai-wiss-dom/verified-context-layer&cloudshell_tutorial=steward/walkthrough_cosmetic.md)**

That walkthrough contains the re-certify command; this file does not. You reach it only after
reading the classification here.

## Conclusion

If the change was substantive, nothing was re-certified — the product remains withheld
pending your investigation, which is the safe default. If it was cosmetic, you re-certified
via the linked walkthrough. Either way no status field was ever hand-flipped: the human
authorizes, the deterministic engine certifies. You can close this tab.
