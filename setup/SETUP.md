# SETUP — reproducible substrate for the Verified Context Layer (native BigQuery)
**Author:** Wissem Khlifi ·


**July 2026**

Stand up everything the VCL demo needs from an (almost) empty GCP project. **Native
BigQuery only** — no Iceberg, no Spark, no @biglake.

## Tooling boundary (why hybrid IaC)

Terraform owns the **static** schema + infra it supports. VCL owns the **dynamic**
verification state. The one thing the Terraform google provider cannot do — write aspect
**content**, create the Data Product, attach assets, load data — is done by bootstrap
scripts, and the verification aspect **values** are written by `vcl.py seal` at runtime.
That split reflects the architecture; it is not a workaround.

| Concern | Owner |
|---|---|
| APIs, datasets, views, aspect-type **schema**, DQ scan, service accounts, IAM | Terraform |
| Data load, Data Product + asset attach, overview/documentation aspect **content** | bootstrap scripts |
| verification aspect **values** (source_tier, anchors, certified_text) | `vcl.py seal` (runtime) |

## Prerequisites

- `terraform` (>= 1.5), `gcloud`, `bq`, and the repo's Python venv (`.venv`).
- Auth: `gcloud auth login` and `gcloud auth application-default login`.
- Config comes from two gitignored files (copy the committed examples):
  ```bash
  cp .env.example .env                                  # repo root — shared by demo + setup
  cp setup/terraform/terraform.tfvars.example setup/terraform/terraform.tfvars
  # edit both: real project_id / project_number / owner_email, location=us-central1
  ```
- `location` must be a single Dataplex region (e.g. `us-central1`) — Dataplex datascans are
  **not** available in the `us` multi-region. TheLook public data is US-multiregion, so
  `01_load_data.sh` cross-region-copies it in before transforming (handled for you).

Set `VCL_DP_RESOURCE` / `VCL_ASPECT_TYPE` in `.env` using the **project number**:
```
VCL_ASPECT_TYPE=projects/<NUMBER>/locations/us-central1/aspectTypes/verification
VCL_DP_RESOURCE=projects/<NUMBER>/locations/us-central1/entryGroups/@dataplex/entries/projects/<NUMBER>/locations/us-central1/dataProducts/ecommerce-customer-intelligence
```

## Step 0 — fresh-project bootstrap (empty project)

**Operator IAM roles.** The human running this must already hold these on the target
project (or `roles/owner`, which subsumes them). Verified against a from-scratch run:

| Role | Why |
|---|---|
| `roles/serviceusage.serviceUsageAdmin` | enable the APIs (Step 0 apply) |
| `roles/iam.serviceAccountAdmin` | create the validator/wrapper/triage service accounts |
| `roles/resourcemanager.projectIamAdmin` | grant the least-priv roles to those SAs |
| `roles/bigquery.admin` | datasets, tables, views, load/cross-region-copy jobs |
| `roles/dataplex.admin` | aspect-types, datascans, Data Products, entries/aspects |
| `roles/aiplatform.user` | run the demo agent (Vertex Gemini) under operator creds |

`serviceusage.googleapis.com` must ALREADY be enabled (it is on by default) — it is what
lets Terraform enable everything else.

**Operator's Data Products role (KC UI).** `iam.tf` also grants the DP owner
(`var.owner_email`) `roles/dataplex.dataProductsAdmin`. This is required to list/manage
Data Products in the Knowledge Catalog UI: project **Owner**'s *implied*
`dataplex.dataProducts.list` is NOT enough — the console gates on an explicit dataProducts
role binding.

**APIs enabled by Terraform** (`apis.tf`, derived from this run — not guessed):
`serviceusage`, `cloudresourcemanager`, `iam`, `bigquery`, `bigquerystorage`, `dataplex`,
`aiplatform`, `datalineage`. On a fresh project the ones typically OFF are `iam`
(needed for SA creation), `cloudresourcemanager` (needed for IAM bindings), `aiplatform`,
and `datalineage` — enabling them is exactly what Step 0 does.

```bash
cd setup/terraform && terraform init

# STEP 0 (TF): enable APIs FIRST, then wait for propagation (time_sleep, 90s).
terraform apply -target=google_project_service.services -target=time_sleep.api_propagation
```

## Required order (dependencies are real — do not reorder)

The order interleaves Terraform and scripts, so after Step 0 Terraform applies in **two
phases** (views + datascan depend on data that a script loads).

```bash
# PHASE 1 (TF): datasets, service accounts + IAM, aspect-type schema
# (all gated behind time_sleep.api_propagation from Step 0)
terraform apply \
  -target=google_bigquery_dataset.base \
  -target=google_bigquery_dataset.views \
  -target=google_service_account.validator \
  -target=google_service_account.wrapper \
  -target=google_service_account.triage \
  -target=google_project_iam_member.validator \
  -target=google_project_iam_member.wrapper \
  -target=google_project_iam_member.triage \
  -target=google_project_iam_member.operator_data_products \
  -target=google_dataplex_aspect_type.verification
cd ../..

# STEP 2 (script): load TheLook subset -> native base tables (customers, orders)
bash setup/bootstrap/01_load_data.sh

# PHASE 2 (TF): views (customers_safe, orders) + DQ scan (customers-quality)
cd setup/terraform && terraform apply && cd ../..

# Run the DQ scan once so it has a result (else vcl.py seal skips the quality anchor)
set -a; source .env; set +a
gcloud dataplex datascans run "$VCL_QUALITY_SCAN_ID" --location="$VCL_LOCATION" --project="$VCL_PROJECT"
# wait until it reports a dataQualityResult:
until gcloud dataplex datascans describe "$VCL_QUALITY_SCAN_ID" --location="$VCL_LOCATION" \
      --project="$VCL_PROJECT" --view=FULL --format="value(dataQualityResult.passed)" | grep -q .; do
  echo "waiting for scan result..."; sleep 10; done

# STEP 6 + 7 (scripts): create Data Product + attach asset, then write governed aspects
bash setup/bootstrap/02_create_dp.sh
bash setup/bootstrap/03_write_aspects.sh

# STEP 8 (runtime): seal — writes the verification aspect values (3 anchors, verified)
bash setup/bootstrap/seal.sh
```

## Round-trip verification (read live — never trust apply/script success)

```bash
set -a; source .env; set +a
DP_ENTRY="${VCL_DP_RESOURCE#*/entries/}"

# 1. customers_safe has NO PII columns (safety invariant)
bq show --schema "${VCL_PROJECT}:${VCL_VIEWS_DATASET}.customers_safe"

# 2. DQ scan has the 3 rules
gcloud dataplex datascans describe "$VCL_QUALITY_SCAN_ID" --location="$VCL_LOCATION" \
  --project="$VCL_PROJECT" --view=FULL

# 3. verification aspect-type has the v8 fields (incl. certified_text)
gcloud dataplex aspect-types describe verification --location="$VCL_LOCATION" --project="$VCL_PROJECT"

# 4. Data Product context (overview: safe-view pointer + PII rule + JOIN)
#    via lookup_context (see verification helper in SETUP), or:
gcloud dataplex entries lookup "$DP_ENTRY" --entry-group="$VCL_ENTRY_GROUP" \
  --location="$VCL_LOCATION" --project="$VCL_PROJECT" --view=CUSTOM \
  --aspect-types="projects/dataplex-types/locations/global/aspectTypes/overview"

# 5 + 6. seal (3 anchors, verified) and check (VERIFIED)
bash setup/bootstrap/seal.sh
python3 src/vcl.py check --project "$VCL_PROJECT" --project-number "$VCL_PROJECT_NUMBER" \
  --location "$VCL_LOCATION" --entry-group "$VCL_ENTRY_GROUP" --dp-entry "$DP_ENTRY" \
  --dp-resource "$VCL_DP_RESOURCE" --aspect-type "$VCL_ASPECT_TYPE" \
  --quality-scan "customers=${VCL_QUALITY_SCAN_ID}:24"

# 7. audience demo Run A (start the wrapper first): builds a PII-free audience
export VCL_TOKEN=$(gcloud auth print-access-token)
python3 src/vcl_wrapper.py &            # in its own shell
python3 vcl_audience_demo/run_demo.py
```

## Teardown

```bash
set -a; source .env; set +a
DP_ID="${VCL_DP_ID:-ecommerce-customer-intelligence}"
TOKEN=$(gcloud auth print-access-token)
BASE="https://dataplex.googleapis.com/v1/projects/${VCL_PROJECT}/locations/${VCL_LOCATION}"

# Data Product + asset are NOT Terraform-managed — delete via REST first:
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" "${BASE}/dataProducts/${DP_ID}/dataAssets/customers"
curl -s -X DELETE -H "Authorization: Bearer $TOKEN" "${BASE}/dataProducts/${DP_ID}"

# Everything else (datasets + tables/views, aspect-type, DQ scan, SAs, IAM):
cd setup/terraform && terraform destroy
# APIs are left enabled on purpose (disable_on_destroy=false).
```

## Guardrails
- Do NOT modify `src/vcl.py`, `src/vcl_wrapper.py`, `src/vcl_triage.py`, or `vcl_audience_demo/`.
- No Iceberg / Spark / @biglake — native BigQuery only.
- Terraform only for provider-supported resources; everything else is a script.
- No real project id / number / email as literals — all via `.env` / `terraform.tfvars`.
- `customers_safe` MUST have no email/first_name/last_name column (verification step 1).
