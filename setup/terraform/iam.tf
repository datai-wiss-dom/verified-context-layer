# The three VCL identities and their LEAST-PRIVILEGE roles (the production hardening seam
# documented in the reference build). The local demo runs under the operator's own creds;
# these SAs exist so the trust/plane boundary is real infrastructure, not just prose:
#
#   validator (vcl.py)      — deterministic core, AI-FREE. Reads BQ etags + scan results,
#                             reads/writes catalog aspects. NO aiplatform.
#   wrapper   (vcl_wrapper) — runtime gate, READ-ONLY catalog. Most exposed => least priv.
#   triage    (vcl_triage)  — advisory, the ONLY identity with model access (aiplatform.user).

resource "google_service_account" "validator" {
  project      = var.project_id
  account_id   = "vcl-validator"
  display_name = "VCL validator (vcl.py) — deterministic, AI-free"
  depends_on   = [time_sleep.api_propagation]
}

resource "google_service_account" "wrapper" {
  project      = var.project_id
  account_id   = "vcl-wrapper"
  display_name = "VCL wrapper — runtime gate, read-only catalog"
  depends_on   = [time_sleep.api_propagation]
}

resource "google_service_account" "triage" {
  project      = var.project_id
  account_id   = "vcl-triage"
  display_name = "VCL triage — advisory, model access only"
  depends_on   = [time_sleep.api_propagation]
}

locals {
  validator_roles = [
    "roles/dataplex.catalogEditor",     # read + write verification aspects on entries
    "roles/dataplex.dataScanDataViewer", # read the DQ scan result (quality anchor)
    "roles/bigquery.metadataViewer",     # read base-table etags/schema (technical anchor)
    "roles/bigquery.jobUser",            # run the reads it needs
  ]
  wrapper_roles = [
    "roles/dataplex.catalogViewer", # read stored verdicts only
  ]
  triage_roles = [
    "roles/dataplex.catalogViewer", # read pinned drift text
    "roles/aiplatform.user",        # the only identity allowed model access
  ]
}

resource "google_project_iam_member" "validator" {
  for_each = toset(local.validator_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.validator.email}"
}

resource "google_project_iam_member" "wrapper" {
  for_each = toset(local.wrapper_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.wrapper.email}"
}

resource "google_project_iam_member" "triage" {
  for_each = toset(local.triage_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.triage.email}"
}

# The human operator (DP owner) needs the EXPLICIT Data Products role to list/manage Data
# Products in the Knowledge Catalog UI. Project Owner's *implied* dataplex.dataProducts.list
# is NOT sufficient for that page (confirmed live) — the console gates on an explicit
# dataProducts role binding. Granted to var.owner_email so it is not a hardcoded literal.
resource "google_project_iam_member" "operator_data_products" {
  project    = var.project_id
  role       = "roles/dataplex.dataProductsAdmin"
  member     = "user:${var.owner_email}"
  depends_on = [time_sleep.api_propagation]
}
