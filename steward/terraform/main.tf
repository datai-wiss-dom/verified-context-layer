# Author: Wissem Khlifi · July 2026
# Steward workflow infra. Terraform owns the STATIC schema (the Governance Drift
# aspect-TYPE). The aspect CONTENT is written by a script (steward/bin/write_drift_aspect.sh),
# because the provider cannot write aspect content (ARCHITECTURE §4).
#
# The Governance Drift aspect is DISPLAY ONLY (PHASE_SPEC_STEWARD_WORKFLOW): it shows the
# steward the pending-review state + the advisory AI triage read, on the entry. The
# wrapper's GATE MUST NEVER read it — the only gate input is the `verification` aspect's
# source_tier. (INV check: grep the wrapper for Governance-Drift/PENDING_REVIEW → nothing.)

resource "google_dataplex_aspect_type" "governance_drift" {
  aspect_type_id = "governance-drift"
  project        = var.project_id
  location       = var.location

  metadata_template = file("${path.module}/../../schemas/governance_drift.json")
}

output "governance_drift_aspect_type" {
  value = google_dataplex_aspect_type.governance_drift.name
}

# --- Push alert plumbing (topic + subscription) ------------------------------
# The alert is published by a SEPARATE watcher (steward/bin/drift_watcher.py) that READS
# the verdict and publishes — NOT by modifying vcl.py's enforce (PHASE_SPEC STOP trigger:
# do not touch the core). In production a push subscription would fan out to email/chat;
# for the demo we use a pull subscription so the message (with the deep link) can be read
# back and shown.
resource "google_project_service" "pubsub" {
  project            = var.project_id
  service            = "pubsub.googleapis.com"
  disable_on_destroy = false
}

resource "google_pubsub_topic" "drift_alerts" {
  project    = var.project_id
  name       = "vcl-governance-drift-alerts"
  depends_on = [google_project_service.pubsub]
}

resource "google_pubsub_subscription" "drift_alerts_pull" {
  project = var.project_id
  name    = "vcl-governance-drift-alerts-sub"
  topic   = google_pubsub_topic.drift_alerts.id
}

output "drift_alerts_topic" {
  value = google_pubsub_topic.drift_alerts.name
}
