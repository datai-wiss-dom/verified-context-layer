# All identifiers via tfvars (gitignored). No hardcoded project/number/email (§6).

variable "project_id" {
  type        = string
  description = "GCP project that owns the catalog + triage SA (the audit store lives here)."
}

variable "location" {
  type        = string
  description = "Firestore location_id (verified valid: us-central1). Match the rest of VCL."
  default     = "us-central1"
}

variable "audit_database" {
  type        = string
  description = "Dedicated Firestore database id for the triage audit store (NOT the (default) db)."
  default     = "vcl-audit"
}

variable "triage_account_id" {
  type        = string
  description = "account_id of the triage service account created in setup/ (the ONLY identity granted audit access)."
  default     = "vcl-triage"
}

locals {
  triage_sa_email = "${var.triage_account_id}@${var.project_id}.iam.gserviceaccount.com"
}
