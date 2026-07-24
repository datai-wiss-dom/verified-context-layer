# Author: Wissem Khlifi · July 2026
# Deploy the VCL wrapper as a Cloud Run service with a dedicated, least-privilege,
# Dataplex READ-ONLY service account. Validator + triage are out of scope here.
#
# Order (two-phase, like setup/): apply the APIs + Artifact Registry + SA + IAM first
# (-target below in DEPLOY.md), run deploy/build.sh to push the image, then apply the
# Cloud Run service (which references that image).

# --- APIs (enable + propagate) -----------------------------------------------
locals {
  services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

resource "google_project_service" "services" {
  for_each           = toset(local.services)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "time_sleep" "api_propagation" {
  depends_on      = [google_project_service.services]
  create_duration = "60s"
}

# Cloud Build runs as the default compute service account, which on a fresh project lacks
# access to the build source bucket + Artifact Registry. Grant it the builder role so
# `deploy/build.sh` can build and push. (Derived from the project number — no literal.)
data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_iam_member" "cloudbuild_builder" {
  project    = var.project_id
  role       = "roles/cloudbuild.builds.builder"
  member     = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
  depends_on = [time_sleep.api_propagation]
}

# --- Artifact Registry (holds the wrapper image) -----------------------------
resource "google_artifact_registry_repository" "vcl" {
  project       = var.project_id
  location      = var.location
  repository_id = var.repo_id
  format        = "DOCKER"
  description   = "VCL wrapper container images."
  depends_on    = [time_sleep.api_propagation]
}

# --- Dedicated least-privilege runtime service account -----------------------
# Named *-run to avoid colliding with the setup/ placeholder "vcl-wrapper" SA. This is
# the SA the Cloud Run wrapper actually runs as; it authenticates to Dataplex via ADC.
resource "google_service_account" "wrapper" {
  project      = var.project_id
  account_id   = "vcl-wrapper-run"
  display_name = "VCL wrapper (Cloud Run) — read-only Dataplex"
  depends_on   = [time_sleep.api_propagation]
}

# Read-only. All THREE are required — each verified live via a distinct HTTP 403:
#   catalogViewer      — dataplex.entries.get / aspectTypes.get (the verdict lookupEntry
#                        returns the verification aspect).
#   dataProductsViewer — dataplex.dataProducts.get. A Data Product entry additionally gates
#                        on this; entries.get alone 403s on a DP entry.
#   mcp.toolUser       — mcp.googleapis.com/tools.call. The lookup_context PROXY hits the
#                        Dataplex MCP endpoint, which checks this MCP-specific permission.
# All three are non-writing viewer/user roles.
locals {
  wrapper_roles = [
    "roles/dataplex.catalogViewer",
    "roles/dataplex.dataProductsViewer",
    "roles/mcp.toolUser",
  ]
}

resource "google_project_iam_member" "wrapper_dataplex" {
  for_each = toset(local.wrapper_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.wrapper.email}"
}

# --- Cloud Run service -------------------------------------------------------
# Ingress = ALL so a LOCAL agent can reach it; authentication REQUIRED (no allUsers
# invoker) so the wrapper's Dataplex-reading SA is never exposed anonymously. See
# DEPLOY.md for the internal-only alternative (agent must then run inside the VPC).
resource "google_cloud_run_v2_service" "wrapper" {
  project             = var.project_id
  name                = var.service_name
  location            = var.location
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.wrapper.email
    containers {
      image = local.image
      ports {
        container_port = 8080
      }
      # Config the wrapper reads from env. NO VCL_TOKEN — it uses the SA's ADC.
      env {
        name  = "VCL_PROJECT"
        value = var.project_id
      }
      env {
        name  = "VCL_LOCATION"
        value = var.location
      }
      env {
        name  = "VCL_ASPECT_TYPE"
        value = var.aspect_type
      }
    }
  }

  depends_on = [
    google_project_iam_member.wrapper_dataplex,
    time_sleep.api_propagation,
  ]
}

# Authenticated access: only this identity (the operator/agent) may invoke the service.
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = var.project_id
  location = var.location
  name     = google_cloud_run_v2_service.wrapper.name
  role     = "roles/run.invoker"
  member   = "user:${var.invoker_email}"
}

output "service_url" {
  value       = google_cloud_run_v2_service.wrapper.uri
  description = "The wrapper's HTTPS URL. Point the agent's VCL_WRAPPER_URL at <url>/mcp."
}

output "runtime_service_account" {
  value = google_service_account.wrapper.email
}
