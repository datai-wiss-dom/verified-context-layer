# Author: Wissem Khlifi · July 2026
# All identifiers via tfvars (gitignored). No hardcoded project/number/email.

variable "project_id" {
  type        = string
  description = "GCP project to deploy the wrapper into (same project as the catalog it reads)."
}

variable "location" {
  type        = string
  description = "Region for Cloud Run + Artifact Registry (match the catalog region)."
  default     = "us-central1"
}

variable "aspect_type" {
  type        = string
  description = "Full verification aspect-type resource the wrapper reads (VCL_ASPECT_TYPE), e.g. projects/<number>/locations/us-central1/aspectTypes/verification."
}

variable "service_name" {
  type        = string
  description = "Cloud Run service name (also the image name)."
  default     = "vcl-wrapper"
}

variable "repo_id" {
  type        = string
  description = "Artifact Registry (Docker) repository id."
  default     = "vcl"
}

variable "image_tag" {
  type        = string
  description = "Image tag built by deploy/build.sh and deployed here."
  default     = "latest"
}

variable "invoker_email" {
  type        = string
  description = "Identity granted roles/run.invoker so it can call the authenticated service (the operator/agent). Format: a bare email; bound as user:<email>."
}

locals {
  # deploy/build.sh must push to this exact path.
  image = "${var.location}-docker.pkg.dev/${var.project_id}/${var.repo_id}/${var.service_name}:${var.image_tag}"
}
