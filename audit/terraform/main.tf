# PHASE: triage audit store. Additive infra ONLY — a dedicated Firestore database for the
# triage's append-only advice log, plus datastore.user for the TRIAGE SA scoped to that
# database. Nothing here touches the verdict, the gate, vcl.py, or the wrapper (INV-3).

# Firestore Native API (idempotent; already enabled live, TF adopts it for reproducibility).
resource "google_project_service" "firestore" {
  project            = var.project_id
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}

resource "time_sleep" "api_propagation" {
  depends_on      = [google_project_service.firestore]
  create_duration = "60s"
}

# Dedicated NAMED database (NOT the (default) db). Structural isolation of the audit store:
# its own database resource, its own IAM scope — physical separation, not convention.
resource "google_firestore_database" "audit" {
  project         = var.project_id
  name            = var.audit_database
  location_id     = var.location
  type            = "FIRESTORE_NATIVE"
  deletion_policy = "DELETE" # allow teardown in the demo

  depends_on = [time_sleep.api_propagation]
}

# datastore.user granted to the TRIAGE SA ONLY, scoped BY IAM CONDITION to the vcl-audit
# database. There is no google_firestore_database_iam_* resource in the provider, so
# database-scoping must be a conditional project binding (verified: google_project_iam_member
# supports `condition`).
#
# NOTE (BUILD_GUIDELINES §2): the condition is ACCEPTED + stored at apply (proven by read-
# back), but its FUNCTIONAL correctness — the triage SA can write to vcl-audit and is denied
# elsewhere — is proven LIVE in Step 4 (the same verified-by-role-contents → verified-live
# discipline approved for datastore.user itself). If Step 4's write 403s, adjust this CEL.
resource "google_project_iam_member" "triage_audit" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.triage_sa_email}"

  condition {
    title       = "vcl-audit-database-only"
    description = "Scope the triage SA's Firestore access to the vcl-audit database only (audit isolation)."
    expression  = "resource.name.startsWith(\"projects/${var.project_id}/databases/${var.audit_database}\")"
  }
}

output "audit_database" {
  value       = google_firestore_database.audit.name
  description = "The dedicated audit Firestore database id."
}

output "audit_database_type_location" {
  value = "${google_firestore_database.audit.type} @ ${google_firestore_database.audit.location_id}"
}

output "triage_audit_member" {
  value       = google_project_iam_member.triage_audit.member
  description = "The identity granted datastore.user (scoped to vcl-audit)."
}
