# All identifiers via tfvars (gitignored). No hardcoded project/number/email (§6).

variable "project_id" {
  type        = string
  description = "GCP project that owns the catalog."
}

variable "location" {
  type        = string
  description = "Dataplex region (match the rest of VCL)."
  default     = "us-central1"
}
