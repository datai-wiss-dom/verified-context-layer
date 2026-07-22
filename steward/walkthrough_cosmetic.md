# Governance drift review — {{DP_DISPLAY_NAME}}

<!--
  Cloud Shell Tutorials walkthrough — steward workflow, COSMETIC branch.
  The backend targets THIS file's path in the deep link ONLY when the AI classification is
  "cosmetic":
    https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo={{GIT_REPO_URL}}&cloudshell_tutorial=steward/walkthrough_cosmetic.md

  PARAMETERIZED TEMPLATE. Cloud Shell Tutorials has NO native variable substitution
  (verified), so the backend fills every {{PLACEHOLDER}} for this drift event before
  serving. Placeholders: {{DP_DISPLAY_NAME}} {{DP_RESOURCE}} {{DRIFTED_DIMENSIONS}}
  {{DRIFT_DETECTED_AT}} {{AI_CLASSIFICATION}} {{AI_CHANGED_RULES}} {{AI_REASONING}}
  {{AI_RECOMMENDATION}} and the seal-command args {{PROJECT}} {{PROJECT_NUMBER}}
  {{LOCATION}} {{DP_ENTRY}} {{ASPECT_TYPE}} {{QUALITY_SCAN_MAP}}.

  Directives are ALL documented (verified live): one H1 (#) title; H2 (##) steps; a
  terminal-input code block ($-prefixed) renders a "copy to Cloud Shell" button;
  <walkthrough-spotlight-pointer spotlightId="devshell-activate-button"> is a documented
  spotlightId. Hybrid spotlight: documented spotlight for the terminal only; KC entry
  navigation is plain text (no fragile cssSelector). No real ids/emails — placeholders only.
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

Confirm you agree that the change is cosmetic before re-certifying.

## Re-certify

The change is **cosmetic** — the meaning of the rules is unchanged, so you can re-certify
now. This re-runs the deterministic verifier against the live state; it is not a hand-flip
of a status field.

Click the copy button on the command below to send it to the Cloud Shell terminal
(<walkthrough-spotlight-pointer spotlightId="devshell-activate-button">open the terminal</walkthrough-spotlight-pointer>
if it is not visible), then press **Enter** to run it:

```
$ python3 src/vcl.py seal --project {{PROJECT}} --project-number {{PROJECT_NUMBER}} --location {{LOCATION}} --entry-group @dataplex --dp-entry {{DP_ENTRY}} --dp-resource {{DP_RESOURCE}} --aspect-type {{ASPECT_TYPE}} --quality-scan {{QUALITY_SCAN_MAP}}
```

When it prints `source_tier=verified`, the data product is certified again and the Verified
Context Layer delivers its context to agents once more.

## Conclusion

You re-certified **{{DP_DISPLAY_NAME}}**. The verifier re-fingerprinted the live state and
wrote `source_tier=verified`; agents can ground on it again. You can close this tab.
