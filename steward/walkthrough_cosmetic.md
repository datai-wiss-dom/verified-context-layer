# Governance drift review — cosmetic change

<!--
  Cloud Shell Tutorials walkthrough — steward workflow, COSMETIC branch. The drift watcher
  links THIS file when the advisory AI classification is "cosmetic":
    https://ssh.cloud.google.com/cloudshell/open?cloudshell_git_repo=<PUBLIC_REPO>&cloudshell_tutorial=steward/walkthrough_cosmetic.md

  GENERIC + SELF-DERIVING (no per-drift substitution, safe for a PUBLIC repo):
  - which branch you are in IS the classification (this file = cosmetic).
  - the drift details are shown NATIVELY in the console entry (the deep link opened it) —
    not duplicated here.
  - the re-certify command derives PROJECT + project NUMBER from your Cloud Shell session,
    so no real project ids are baked into this public file.
  Directives are all documented: one H1 title, H2 steps, and a $-prefixed terminal-input
  code block (renders a "copy to Cloud Shell" button). No spotlight-pointer — the only
  documented spotlight for this page (devshell-activate-button) is the "Activate Cloud
  Shell" button, which does not exist while the walkthrough is already running in Cloud
  Shell. The DP id defaults to the demo product; override with `export DP_ID=...`.
-->

## What drifted

A data product you own has **drifted** and is no longer verified. The Verified Context
Layer is currently **withholding** its governed context from agents until it is
re-certified — so this is safe, but it needs your review.

The Google Cloud console has opened on this data product's catalog **entry** alongside this
guide. On that entry, open the **Governance Drift** aspect to see which dimension drifted,
when, and the assistant's read. (That aspect is display-only — editing it certifies
nothing.)

## The AI triage verdict — cosmetic (advisory only)

You are on the **cosmetic** path: the assistant classified this change as **cosmetic**
(the meaning of the rules is unchanged). The console's Governance Drift aspect shows the
full reasoning.

This classification is **advice only** — it is not a verdict and it changes nothing on its
own. Only re-running the deterministic verifier can mark the data product verified again.

## Re-certify

Because the change is cosmetic, you can re-certify now. This re-runs the deterministic
verifier against the live state — it re-fingerprints the data product; it does not flip a
status field.

First make sure your project is set (the tab that opened this guide is already in your
project; if `gcloud config get-value project` is empty, run
`gcloud config set project YOUR_PROJECT`). Then click the copy button on the command below
to send it to the Cloud Shell terminal and press **Enter**:

```
$ PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"; NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"; DP_ID="${DP_ID:-ecommerce-customer-intelligence}"; python3 src/vcl.py seal --project "$PROJECT" --project-number "$NUMBER" --location us-central1 --entry-group @dataplex --dp-entry "projects/$NUMBER/locations/us-central1/dataProducts/$DP_ID" --dp-resource "projects/$NUMBER/locations/us-central1/entryGroups/@dataplex/entries/projects/$NUMBER/locations/us-central1/dataProducts/$DP_ID" --aspect-type "projects/$NUMBER/locations/us-central1/aspectTypes/verification" --quality-scan "customers=customers-quality:24" && python3 steward/bin/write_drift_aspect.py --resolve
```

When it prints `source_tier=verified`, the data product is certified again and the Verified
Context Layer delivers its context to agents once more. The command then flips the
Governance Drift aspect on the entry from `PENDING_REVIEW` to `RESOLVED` (display-only
housekeeping — the gate never reads that aspect; the deterministic seal is what actually
certified the product).

## Conclusion

You re-certified the data product by re-running the deterministic verifier. Its
`source_tier` is `verified` again and agents can ground on it. You can close this tab.
