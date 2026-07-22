#!/usr/bin/env bash
# Step 2 — load a native-BigQuery subset of TheLook into the base dataset.
#
# TheLook (bigquery-public-data.thelook_ecommerce) is US multi-region; our datasets are in
# a single region (var.location, e.g. us-central1) so Dataplex can scan them. A same-job
# CTAS cannot read US and write us-central1, so we FIRST cross-region-copy the two raw
# source tables into the base dataset (bq cp supports cross-region), THEN transform them
# in-region and drop the staging tables.
#
# DERIVED columns (TheLook has neither natively — this is the one thing derived, honestly):
#   customer_segment : age cohort  (age<=27 Gen-Z, <=43 Millennial, <=59 Gen-X, else Boomer;
#                                    ages are 12-70 with no nulls, so every row gets a valid
#                                    segment — SegmentValid passes)
#   lifetime_value   : SUM(order_items.sale_price) WHERE status='Complete', per user
#   orders.payment_method : NOT in TheLook — synthesized deterministically from the id.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
set -a; source "$REPO_ROOT/.env"; set +a

: "${VCL_PROJECT:?}"; : "${VCL_LOCATION:?}"
DS="${VCL_BASE_DATASET:-ecommerce}"
SRC="bigquery-public-data:thelook_ecommerce"

echo ">> [1/4] cross-region copy raw TheLook -> ${VCL_PROJECT}:${DS} (staging)"
bq cp -f bigquery-public-data:thelook_ecommerce.users       "${VCL_PROJECT}:${DS}._raw_users"
bq cp -f bigquery-public-data:thelook_ecommerce.order_items "${VCL_PROJECT}:${DS}._raw_order_items"

echo ">> [2/4] build native customers (derive segment + lifetime_value)"
bq --location="${VCL_LOCATION}" query --use_legacy_sql=false --project_id="${VCL_PROJECT}" "
CREATE OR REPLACE TABLE \`${VCL_PROJECT}.${DS}.customers\` AS
SELECT
  CAST(u.id AS STRING)                       AS customer_id,
  u.first_name, u.last_name, u.email,
  u.country, u.city,
  DATE(u.created_at)                         AS signup_date,
  CASE
    WHEN u.age <= 27 THEN 'Gen-Z'
    WHEN u.age <= 43 THEN 'Millennial'
    WHEN u.age <= 59 THEN 'Gen-X'
    ELSE 'Boomer'
  END                                        AS customer_segment,
  COALESCE(ltv.lifetime_value, 0.0)          AS lifetime_value
FROM \`${VCL_PROJECT}.${DS}._raw_users\` u
LEFT JOIN (
  SELECT user_id, SUM(sale_price) AS lifetime_value
  FROM \`${VCL_PROJECT}.${DS}._raw_order_items\`
  WHERE status = 'Complete'
  GROUP BY user_id
) ltv ON u.id = ltv.user_id;
"

echo ">> [3/4] build native orders (line-item grain; synthetic payment_method)"
bq --location="${VCL_LOCATION}" query --use_legacy_sql=false --project_id="${VCL_PROJECT}" "
CREATE OR REPLACE TABLE \`${VCL_PROJECT}.${DS}.orders\` AS
SELECT
  CAST(oi.order_id AS STRING)                AS order_id,
  CAST(oi.user_id AS STRING)                 AS customer_id,
  CAST(oi.product_id AS STRING)              AS product_id,
  DATE(oi.created_at)                        AS order_date,
  1                                          AS quantity,
  oi.sale_price                              AS unit_price,
  oi.sale_price                              AS total_amount,
  oi.status                                  AS status,
  ['Credit Card','PayPal','Debit Card','Gift Card'][OFFSET(MOD(oi.id, 4))] AS payment_method
FROM \`${VCL_PROJECT}.${DS}._raw_order_items\` oi;
"

echo ">> [4/4] drop staging + report row counts"
bq rm -f -t "${VCL_PROJECT}:${DS}._raw_users"
bq rm -f -t "${VCL_PROJECT}:${DS}._raw_order_items"
bq --location="${VCL_LOCATION}" query --use_legacy_sql=false --project_id="${VCL_PROJECT}" "
SELECT 'customers' AS t, COUNT(*) n FROM \`${VCL_PROJECT}.${DS}.customers\`
UNION ALL SELECT 'orders', COUNT(*) FROM \`${VCL_PROJECT}.${DS}.orders\`
ORDER BY t;
"
echo ">> load complete."
