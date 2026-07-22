# Data-quality scan on the native base `customers` table (PHASE 2 — the table must exist).
# Three rules, INVERTED logic: each SQL assertion PASSES when it finds ZERO bad rows.
# ${data()} is the scan's bound table — it is escaped as $${data()} so Terraform passes it
# through literally instead of trying to interpolate it. Rule names are alphanumeric only.
#
# NOTE: creating the scan does not run it. Run it once (SETUP.md) before `vcl.py seal`, or
# the quality anchor is skipped and seal writes only 2 anchors.

resource "google_dataplex_datascan" "customers_quality" {
  project      = var.project_id
  location     = var.location
  data_scan_id = var.quality_scan_id

  data {
    resource = "//bigquery.googleapis.com/projects/${var.project_id}/datasets/${var.base_dataset}/tables/customers"
  }

  execution_spec {
    trigger {
      on_demand {}
    }
  }

  data_quality_spec {
    rules {
      name      = "SegmentValid"
      dimension = "VALIDITY"
      column    = "customer_segment"
      sql_assertion {
        sql_statement = "SELECT * FROM $${data()} WHERE customer_segment NOT IN ('Gen-Z','Millennial','Gen-X','Boomer')"
      }
    }

    rules {
      name      = "LTVNotNegative"
      dimension = "VALIDITY"
      column    = "lifetime_value"
      sql_assertion {
        sql_statement = "SELECT * FROM $${data()} WHERE lifetime_value < 0"
      }
    }

    rules {
      name                  = "EmailNotNull"
      dimension             = "COMPLETENESS"
      column                = "email"
      non_null_expectation {}
    }
  }

  depends_on = [time_sleep.api_propagation]
}
