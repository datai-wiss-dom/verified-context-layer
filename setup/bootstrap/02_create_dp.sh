#!/usr/bin/env bash
# Step 6 — create the Data Product and attach the native `customers` table as its asset.
# REST (the Terraform provider does not support Data Product creation / asset attach).
#   create : POST  .../dataProducts?dataProductId=<id>
#   attach : POST  .../dataProducts/<id>/dataAssets?dataAssetId=customers  {resource: <uri>}
# The asset URI lands in the DP's data-product aspect assets[], which is exactly what
# vcl.py reads to build the technical anchor.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
set -a; source "$REPO_ROOT/.env"; set +a

: "${VCL_PROJECT:?}"; : "${VCL_LOCATION:?}"; : "${VCL_OWNER_EMAIL:?}"
DS="${VCL_BASE_DATASET:-ecommerce}"
DP_ID="${VCL_DP_ID:-ecommerce-customer-intelligence}"
BASE="https://dataplex.googleapis.com/v1/projects/${VCL_PROJECT}/locations/${VCL_LOCATION}"
TOKEN="$(gcloud auth print-access-token)"
ASSET_URI="//bigquery.googleapis.com/projects/${VCL_PROJECT}/datasets/${DS}/tables/customers"

echo ">> [1/3] create Data Product ${DP_ID}"
BODY="$(cat <<JSON
{
  "displayName": "Customer Intelligence",
  "description": "Governed source of truth for customer analytics. 100,000 customers segmented by age cohort (Gen-Z, Millennial, Gen-X, Boomer) with pre-calculated Customer Lifetime Value. BUSINESS RULES: lifetime_value = SUM of completed orders per customer - pre-calculated, do not re-derive. customer_segment is the primary analytical dimension. email column is PII - never expose in outputs. DATA OWNER: Customer Analytics Team.",
  "labels": { "domain": "customer", "sensitivity": "pii", "agent-ready": "true" },
  "ownerEmails": [ "${VCL_OWNER_EMAIL}" ]
}
JSON
)"
OP=$(curl -s -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  "${BASE}/dataProducts?dataProductId=${DP_ID}" -d "${BODY}" \
  | .venv/bin/python -c "import sys,json; print(json.load(sys.stdin).get('name',''))" || true)
echo "   create operation: ${OP:-<none / may already exist>}"

echo ">> [2/3] wait for the create operation to finish (DP not attachable until done)"
# Poll the LRO to done=true. A GET returning 200 is NOT sufficient — the asset attach
# fails with FAILED_PRECONDITION until the create operation completes.
for i in $(seq 1 20); do
  if [ -n "$OP" ]; then
    done=$(curl -s -H "Authorization: Bearer ${TOKEN}" "https://dataplex.googleapis.com/v1/${OP}" \
      | .venv/bin/python -c "import sys,json; print(json.load(sys.stdin).get('done', False))" 2>/dev/null || echo False)
    [ "$done" = "True" ] && { echo "   DP create complete (op done)"; break; }
  fi
  echo "   waiting ($i)..."; sleep 3
done

echo ">> [3/3] attach the customers table asset"
curl -s -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  "${BASE}/dataProducts/${DP_ID}/dataAssets?dataAssetId=customers" \
  -d "{\"resource\": \"${ASSET_URI}\"}" | .venv/bin/python -m json.tool | head -20 || true

echo ">> waiting for asset attach to settle"; sleep 20
echo ">> data-product aspect assets[] now:"
gcloud dataplex entries lookup \
  "projects/${VCL_PROJECT_NUMBER}/locations/${VCL_LOCATION}/dataProducts/${DP_ID}" \
  --entry-group="${VCL_ENTRY_GROUP:-@dataplex}" --location="${VCL_LOCATION}" \
  --project="${VCL_PROJECT}" --view=FULL --format=json 2>/dev/null \
  | .venv/bin/python -c "
import sys,json
d=json.load(sys.stdin)
for k,v in d.get('aspects',{}).items():
    if 'data-product' in k:
        print(json.dumps(v.get('data',{}).get('assets',[]), indent=2))
"
echo ">> DP + asset done."
