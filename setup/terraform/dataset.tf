# Two datasets, both in var.location:
#   base_dataset  — native base tables (customers, orders), loaded by 01_load_data.sh
#   views_dataset — governed views (customers_safe, orders), created in views.tf
# Two datasets (not one) because there is both a base `orders` table and an `orders`
# view; they cannot share a dataset.

resource "google_bigquery_dataset" "base" {
  project                    = var.project_id
  dataset_id                 = var.base_dataset
  location                   = var.location
  description                = "Native base tables loaded from TheLook (customers, orders)."
  delete_contents_on_destroy = true

  depends_on = [time_sleep.api_propagation]
}

resource "google_bigquery_dataset" "views" {
  project                    = var.project_id
  dataset_id                 = var.views_dataset
  location                   = var.location
  description                = "Governed views the agent may query (customers_safe = PII-safe, orders)."
  delete_contents_on_destroy = true

  depends_on = [time_sleep.api_propagation]
}
