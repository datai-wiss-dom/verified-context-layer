# Author: Wissem Khlifi · July 2026
# Provider + version pins. Terraform owns STATIC schema + infra; VCL owns the DYNAMIC
# verification state (aspect values written by vcl.py seal at runtime). The one thing the
# provider cannot do — write aspect CONTENT / create the Data Product / load data — is
# handled by the bootstrap scripts. That boundary reflects the architecture, not a hack.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.location
}
