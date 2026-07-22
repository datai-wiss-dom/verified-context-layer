#!/usr/bin/env bash
# Step 7 — write the governed context the AGENT grounds on: the overview + queries aspects
# on the DP entry (REST/gcloud; the Terraform provider cannot write aspect content).
# MUST include: the PII rule, the PII-SAFE view pointer (customers_safe = only export
# surface), the sanctioned JOIN, lifetime_value pre-calc, segment enum, 90-day-lapsed rule.
# Gotchas baked in: queries aspect needs userManaged:true; field is 'sql' not 'query';
# sqlDialect 'GOOGLE_SQL'; overview/queries are GLOBAL aspect types (dataplex-types project).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
set -a; source "$REPO_ROOT/.env"; set +a

: "${VCL_PROJECT:?}"; : "${VCL_PROJECT_NUMBER:?}"; : "${VCL_LOCATION:?}"
VIEWS="${VCL_VIEWS_DATASET:-ecommerce_views}"
DP_ID="${VCL_DP_ID:-ecommerce-customer-intelligence}"
EG="${VCL_ENTRY_GROUP:-@dataplex}"
DP_ENTRY="projects/${VCL_PROJECT_NUMBER}/locations/${VCL_LOCATION}/dataProducts/${DP_ID}"

# Derive the dataplex-types GLOBAL project number from an existing global aspect key
# (e.g. the data-product aspect written at asset-attach) — no hardcoded literal.
GLOBAL_NUM="$(gcloud dataplex entries lookup "$DP_ENTRY" --entry-group="$EG" \
  --location="$VCL_LOCATION" --project="$VCL_PROJECT" --view=FULL --format=json 2>/dev/null \
  | .venv/bin/python -c "
import sys,json
d=json.load(sys.stdin)
for k in d.get('aspects',{}):
    if k.endswith('.global.data-product') or '.global.overview' in k:
        print(k.split('.',1)[0]); break
")"
: "${GLOBAL_NUM:?could not derive dataplex-types global project number from DP aspects}"
echo ">> dataplex-types global project number: ${GLOBAL_NUM}"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

VCL_PROJECT="$VCL_PROJECT" VIEWS="$VIEWS" GLOBAL_NUM="$GLOBAL_NUM" \
.venv/bin/python - "$TMP" <<'PY'
import json, os, sys
tmp = sys.argv[1]
proj = os.environ["VCL_PROJECT"]; views = os.environ["VIEWS"]; g = os.environ["GLOBAL_NUM"]
safe   = f"{proj}.{views}.customers_safe"
orders = f"{proj}.{views}.orders"

overview = (
    "<p># Customer Intelligence — Data Product\n\n"
    "## Business Rules (Agent-Enforced)\n"
    "- `lifetime_value` is PRE-CALCULATED — do NOT re-derive from the orders table.\n"
    "- `email`, `first_name`, `last_name` are PII — NEVER expose in any output, export, "
    "audience artifact, session state, or briefing.\n"
    "- `customer_segment` values: Gen-Z | Millennial | Gen-X | Boomer.\n"
    "- `signup_date` — use for tenure analysis (days since signup).\n\n"
    "## Agent Consumption Instructions\n"
    f"- Query customers via the PII-SAFE view: `{safe}` — columns: customer_id, country, "
    "city, signup_date, customer_segment, lifetime_value. Excludes email/first_name/"
    "last_name by construction and is the ONLY sanctioned surface for building exports.\n"
    f"- Query order history via: `{orders}` — columns: order_id, customer_id, product_id, "
    "order_date, quantity, unit_price, total_amount, status, payment_method.\n"
    f"- SANCTIONED JOIN pattern: `{safe}` AS c JOIN `{orders}` AS o "
    "ON c.customer_id = o.customer_id.\n"
    "- Lapsed / \"has not ordered recently\": compute each customer's most recent "
    "o.order_date and compare to CURRENT_DATE() (e.g. no order in the last 90 days).\n"
    "- High-value: use `lifetime_value` directly — do not recalculate.\n"
    "- Audience / export artifacts: select customer_id + customer_segment + lifetime_value; "
    "NEVER include email or any PII.\n\n"
    "## Data Quality\n"
    "- Quality scan `customers-quality` — 3 rules (SegmentValid, LTVNotNegative, "
    "EmailNotNull).</p>"
)

queries = {
    "queries": [
        {
            "description": "Win-back audience — high-value customers with no order in the last 90 days (PII-safe: no email)",
            "source": "USER",
            "sql": (
                "SELECT c.customer_id, c.customer_segment, ROUND(c.lifetime_value, 2) AS lifetime_value "
                f"FROM `{safe}` AS c LEFT JOIN `{orders}` AS o ON c.customer_id = o.customer_id "
                "GROUP BY c.customer_id, c.customer_segment, c.lifetime_value "
                "HAVING MAX(o.order_date) < DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) "
                "AND c.lifetime_value > 500 ORDER BY lifetime_value DESC"
            ),
            "sqlDialect": "GOOGLE_SQL",
        },
    ],
    "userManaged": True,
}

json.dump({f"{g}.global.overview": {"data": {"content": overview, "links": []}}},
          open(os.path.join(tmp, "overview.json"), "w"))
json.dump({f"{g}.global.queries": {"data": queries}},
          open(os.path.join(tmp, "queries.json"), "w"))
print("payloads written")
PY

echo ">> PATCH overview aspect"
gcloud dataplex entries update-aspects "$DP_ENTRY" --entry-group="$EG" \
  --location="$VCL_LOCATION" --project="$VCL_PROJECT" --aspects="$TMP/overview.json" >/dev/null
echo ">> PATCH queries aspect"
gcloud dataplex entries update-aspects "$DP_ENTRY" --entry-group="$EG" \
  --location="$VCL_LOCATION" --project="$VCL_PROJECT" --aspects="$TMP/queries.json" >/dev/null
echo ">> aspects written."
