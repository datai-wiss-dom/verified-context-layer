# Author: Wissem Khlifi · July 2026
# ALL identifiers come from here (fed by terraform.tfvars, gitignored). NO real project
# id / number / email as literals anywhere in the committed config.

variable "project_id" {
  type        = string
  description = "GCP project id to build into."
}

variable "project_number" {
  type        = string
  description = "GCP project number (used for the aspect-type key and cross-checks)."
}

variable "location" {
  type        = string
  description = "Region for BigQuery + Dataplex. Must be a single Dataplex region (NOT the 'us' multi-region — Dataplex datascans are regional)."
  default     = "us-central1"
}

variable "base_dataset" {
  type        = string
  description = "Dataset holding the native base tables (customers, orders)."
  default     = "ecommerce"
}

variable "views_dataset" {
  type        = string
  description = "Dataset holding the governed views (customers_safe, orders). Fixed to 'ecommerce_views' because the demo agent references that dataset name and the demo is out of scope to modify."
  default     = "ecommerce_views"
}

variable "owner_email" {
  type        = string
  description = "Data Product owner email (used by the DP creation script, not by Terraform). Declared here so tfvars carries a single source of truth."
}

variable "dp_id" {
  type        = string
  description = "Data Product id."
  default     = "ecommerce-customer-intelligence"
}

variable "quality_scan_id" {
  type        = string
  description = "Data-quality scan id (also used in the vcl.py seal --quality-scan mapping)."
  default     = "customers-quality"
}
