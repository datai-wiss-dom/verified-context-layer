# Setup Spec — reproducible bootstrap for Verified Context Layer (native BigQuery)


Goal: stand up the full substrate the VCL demo needs from an empty GCP project, one
documented sequence. SIMPLIFIED from the original lakehouse demo: NO Iceberg, NO Spark,
NO @biglake. VCL verifies CONTEXT; it does not care about storage format, so the Iceberg
lakehouse layer is dropped. Data lands in NATIVE BigQuery. This makes setup simpler and
sharpens VCL's focus (verification currency, not lakehouse plumbing).


Hybrid IaC: Terraform for what the Google provider supports; a bootstrap script for what
it does not; `vcl.py seal` as the runtime finish.


## Provider coverage (VERIFIED 2026-07-21 — do not re-litigate)
Terraform google provider SUPPORTS: google_bigquery_dataset, google_bigquery_table
(incl. views), IAM, service accounts, google_dataplex_aspect_type,
google_dataplex_datascan.
Does NOT support: attaching aspects to entries / writing aspect CONTENT (open issue
#19188), Data Product entry creation + asset attachment.
=> aspect content + the Data Product + the data load are done by SCRIPT. The verification
aspect VALUES are written by `vcl.py seal` at runtime (STATE, not infra).


## Architectural boundary (state in README)
Terraform owns STATIC schema + infra. VCL owns DYNAMIC verification state. The one thing
Terraform cannot do (write aspect content) is exactly what is meant to be dynamic and
verified. The tooling boundary reflects the architecture; it is not a workaround.


---


## Required order (dependencies are real — do not reorder)
```
1. [TF]     APIs enabled + BigQuery dataset(s) + service accounts + IAM
2. [SCRIPT] load TheLook subset -> native BigQuery base tables (customers, orders)
3. [TF]     views: customers_safe (PII-safe), orders  (depend on step 2 tables)
4. [TF]     aspect-type: verification (schema, from schemas/verification_v8_certtext.json)
5. [TF]     data-quality scan: customers-quality (on the native BQ customers table)
6. [SCRIPT] create Data Product ecommerce-customer-intelligence + attach the customers asset
7. [SCRIPT] write overview + documentation aspects (the governed context: safe view,
            JOIN, PII rule)
8. [RUNTIME] vcl.py seal  (writes the verification aspect values)
9. [VERIFY]  round-trip every step
```


---


## Layout to produce
```
setup/
  terraform/
    versions.tf     provider + version pins
    variables.tf    project_id, project_number, location, dataset (NO real values)
    apis.tf         google_project_service for dataplex, bigquery, aiplatform
    dataset.tf      bigquery dataset(s) + IAM
    tables.tf       base table SCHEMAS ONLY if TF-managed; else script loads data
    views.tf        customers_safe + orders views
    aspect_type.tf  verification aspect-type (from the committed v8 JSON)
    datascan.tf     customers-quality DQ scan (3 rules, below)
    iam.tf          service accounts (validator / wrapper / triage) + least-priv roles
    terraform.tfvars.example   placeholders only (real tfvars gitignored)
  bootstrap/
    01_load_data.sh      copy TheLook subset -> native BQ base tables
    02_create_dp.sh      create Data Product + attach the customers asset (REST)
    03_write_aspects.sh  overview + documentation aspect content (REST PATCH)
    seal.sh              wraps `python3 src/vcl.py seal` with args from .env
  SETUP.md               human runbook: prereqs, order, exact commands, verify
```


---


## KNOWN definitions (from the reference build — use these, do NOT invent)


### Base data (step 2, script)
Source: TheLook public BigQuery dataset (`bigquery-public-data.thelook_ecommerce`).
Copy the needed columns into native BQ tables in the project's dataset. Minimum:
- customers: customer_id, first_name, last_name, email, country, city, signup_date,
  customer_segment, lifetime_value
  (segment ∈ {Gen-Z, Millennial, Gen-X, Boomer}; lifetime_value pre-calculated =
  SUM completed orders per customer). ~100k rows in the original.
- orders: order_id, customer_id, product_id, order_date, quantity, unit_price,
  total_amount, status, payment_method  (status ∈ Complete/Cancelled/Returned/
  Processing/Shipped). ~181k line items in the original.
  NOTE: TheLook may not have customer_segment / lifetime_value natively — derive them in
  the load (segment by a cohort rule; lifetime_value = SUM(total_amount) WHERE
  status='Complete' per customer). Capture the exact load SQL and keep it in 01_load_data.sh.


### Views (step 3, Terraform)
- customers_safe: SELECT customer_id, country, city, signup_date, customer_segment,
  lifetime_value FROM <dataset>.customers.  MUST EXCLUDE email/first_name/last_name.
  (Verify the created view's schema has no PII columns — safety invariant.)
- orders: passthrough/curated view over <dataset>.orders exposing order_id, customer_id,
  product_id, order_date, quantity, unit_price, total_amount, status, payment_method.


### aspect-type (step 4, Terraform)
Use schemas/verification_v8_certtext.json as the metadata template for
google_dataplex_aspect_type "verification". Top-level fields: verified_against,
verified_at, source_tier, source_etag, anchors[], drift_summary[], drifted_hash,
drift_detected_at, certified_text.


### DQ scan customers-quality (step 5, Terraform) — 3 rules, INVERTED logic
Scan target: the native BQ customers table. Publish results to Knowledge Catalog.
Rule logic: SQL assertion PASSES when the SELECT returns ZERO rows (it finds the BAD
rows). Rule names alphanumeric only.
1. SegmentValid  (VALIDITY, column customer_segment):
   SELECT * FROM ${data()} WHERE customer_segment NOT IN
   ('Gen-Z','Millennial','Gen-X','Boomer')
2. LTVNotNegative (VALIDITY, column lifetime_value):
   SELECT * FROM ${data()} WHERE lifetime_value < 0
3. EmailNotNull  (COMPLETENESS, column email): built-in null check.
   Use ${data()} (do NOT hardcode the table in rule SQL).


### Data Product (step 6, script — REST, no TF resource)
POST dataplex.googleapis.com/v1/projects/${PROJECT}/locations/${LOCATION}/dataProducts?
dataProductId=ecommerce-customer-intelligence
Body: displayName "Customer Intelligence"; the governed description (business rules incl.
"email column is PII - never expose"); ownerEmails from .env (NOT a real literal); labels
{domain:customer, sensitivity:pii, agent-ready:true}.  (Labels: lowercase/digits/hyphens
only - no underscores/commas.) Async: wait ~10s. Then attach the customers table as an
asset.


### Overview/documentation aspects (step 7, script — REST PATCH)
PATCH the DP entry's dataplex-types.global.overview (and documentation) aspects with the
governed context the AGENT needs. MUST include:
- the PII rule (email/first_name/last_name never exposed),
- the PII-SAFE view pointer: <dataset>.customers_safe is the ONLY sanctioned export surface,
- the sanctioned JOIN: customers_safe c JOIN orders o ON c.customer_id = o.customer_id,
- lifetime_value is pre-calculated (do not re-derive), segment enum, 90-day-lapsed rule.
  GOTCHAS (from the reference build): queries aspect needs userManaged:true or 400 'Failed
  to parse'; field is 'sql' not 'query'; sqlDialect 'GOOGLE_SQL'. overview uses aspectType
  projects/dataplex-types/locations/global/aspectTypes/overview.


### seal (step 8, runtime)
`python3 src/vcl.py seal` with the standard args (project, project-number, location,
entry-group @dataplex, dp-entry, aspect-type verification, quality-scan
"customers=customers-quality:24", dp-resource). All args from .env, no literals.


---


## Configuration
- ALL identifiers via variables / .env — NO real project id, number, or email as literals.
- terraform.tfvars gitignored; terraform.tfvars.example placeholders only.


## Round-trip verification (acceptance — read live, never trust apply/script success)
1. `bq show --schema <dataset>.customers_safe` -> customer_id, country, city,
   signup_date, customer_segment, lifetime_value; NO email/first_name/last_name.
2. `gcloud dataplex datascans describe customers-quality --location=LOC --view=FULL`
   -> 3 rules (SegmentValid, LTVNotNegative, EmailNotNull).
3. `gcloud dataplex aspect-types describe verification` -> v8 fields incl certified_text.
4. Data Product exists; lookup_context returns the overview with the customers_safe
   pointer + PII rule + JOIN.
5. `python3 src/vcl.py seal` -> 3 anchors, source_tier=verified.
6. `python3 src/vcl.py check` -> VERIFIED.
7. Audience demo Run A builds a PII-free audience; Run B (after drift+enforce) is refused.


## Guardrails
- Do NOT modify src/vcl.py, src/vcl_wrapper.py, src/vcl_triage.py, or the demo.
- NO Iceberg / Spark / @biglake — native BigQuery only.
- Terraform ONLY for the provider-supported resources listed. Everything else script.
- Use the KNOWN definitions above; the only thing to derive is the exact TheLook load SQL
  (customer_segment + lifetime_value may need computing) - capture it, verify by row count.
- customers_safe MUST have no PII columns - assert it. No real identifiers as literals.