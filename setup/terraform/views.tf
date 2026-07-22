# Governed views (PHASE 2 — apply AFTER 01_load_data.sh, because BigQuery validates a
# view's query against its base table at create time).
#
# customers_safe is the ONLY sanctioned export surface: it EXCLUDES email / first_name /
# last_name by construction. The safety invariant (no PII columns) is asserted live in
# SETUP.md verification step 1.

resource "google_bigquery_table" "customers_safe" {
  project             = var.project_id
  dataset_id          = var.views_dataset
  table_id            = "customers_safe"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        customer_id,
        country,
        city,
        signup_date,
        customer_segment,
        lifetime_value
      FROM `${var.project_id}.${var.base_dataset}.customers`
    SQL
  }

  depends_on = [google_bigquery_dataset.views]
}

resource "google_bigquery_table" "orders" {
  project             = var.project_id
  dataset_id          = var.views_dataset
  table_id            = "orders"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        order_id,
        customer_id,
        product_id,
        order_date,
        quantity,
        unit_price,
        total_amount,
        status,
        payment_method
      FROM `${var.project_id}.${var.base_dataset}.orders`
    SQL
  }

  depends_on = [google_bigquery_dataset.views]
}
