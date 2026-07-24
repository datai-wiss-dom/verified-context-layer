# Author: Wissem Khlifi · July 2026
# STEP 0 — enable every API the substrate needs, on a possibly-EMPTY project. Apply this
# FIRST (see SETUP.md), then let it propagate before anything that consumes it.
#
# The list is DERIVED from a from-scratch run on an empty project, not guessed:
#   serviceusage          — enable other services (must already be on to bootstrap)
#   cloudresourcemanager  — project-level IAM bindings (google_project_iam_member)
#   iam                   — create the validator/wrapper/triage service accounts
#   bigquery              — datasets, tables, views, load jobs
#   bigquerystorage       — Storage Read API (BigQuery client + analytics plugin)
#   dataplex              — aspect-types, datascans, Data Products, catalog aspects
#   aiplatform            — Vertex Gemini (the demo agent + the triage SA)
#   datalineage          — Dataplex lineage capture used by catalog/datascan
# disable_on_destroy=false so a teardown never disables an API another workload may use.

locals {
  services = [
    "serviceusage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com",
    "dataplex.googleapis.com",
    "aiplatform.googleapis.com",
    "datalineage.googleapis.com",
  ]
}

resource "google_project_service" "services" {
  for_each = toset(local.services)

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Propagation handling: newly-enabled APIs are not instantly usable (IAM/SA creation in
# particular races enablement). Gate every downstream resource behind this wait.
resource "time_sleep" "api_propagation" {
  depends_on      = [google_project_service.services]
  create_duration = "90s"
}
