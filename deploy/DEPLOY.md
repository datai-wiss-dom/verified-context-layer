# DEPLOY — VCL wrapper on Cloud Run (Terraform)

Deploys `src/vcl_wrapper.py` as a Cloud Run service with a **dedicated, least-privilege,
Dataplex read-only** service account. Validator job + triage are **out of scope**.

## What changed in the wrapper (auth/serving only — gating logic untouched)
- Token: uses `VCL_TOKEN` if set (local), else the runtime **service account's ADC**
  (`google.auth`) — no passed token on Cloud Run.
- Verdict read: Dataplex **REST `lookupEntry`** instead of shelling to `gcloud` → no gcloud
  in the image.
- Serving: binds **`0.0.0.0:$PORT`** (Cloud Run) instead of `127.0.0.1`.

## Ingress / auth decision
**`ingress = INGRESS_TRAFFIC_ALL` + authentication REQUIRED** (no `allUsers` invoker).
- The demo agent runs **locally**, so it must be able to reach the service — `ingress =
  internal` would require the agent to run inside the VPC (rejected for the local demo).
- Requiring auth (vs. public/unauthenticated) means the wrapper's Dataplex-reading SA is
  never exposed anonymously. Only `var.invoker_email` gets `roles/run.invoker`.
- **Production tightening:** if the agent runs on GCP, switch to `ingress = internal` and
  keep auth — that's stricter. Left as ALL here purely so a laptop agent can connect.

## Prerequisites
- `terraform` (>= 1.5), `gcloud`, Docker not required (build runs in Cloud Build).
- `cp deploy/terraform/terraform.tfvars.example deploy/terraform/terraform.tfvars` and fill
  `project_id`, `location`, `aspect_type` (the verification aspect-type resource), and
  `invoker_email` (the identity that will call the service).
- The catalog substrate must already exist (see `setup/SETUP.md`) — this only deploys the
  wrapper against it.

## Sequence (two-phase, because the Cloud Run service needs the image to exist first)

```bash
cd deploy/terraform && terraform init

# PHASE A: APIs + Artifact Registry + SA + IAM (everything the build/deploy needs)
terraform apply \
  -target=google_project_service.services \
  -target=time_sleep.api_propagation \
  -target=google_artifact_registry_repository.vcl \
  -target=google_service_account.wrapper \
  -target=google_project_iam_member.wrapper_dataplex
cd ../..

# BUILD: build the wrapper image (Cloud Build) and push to Artifact Registry
bash deploy/build.sh

# PHASE B: the Cloud Run service + its invoker binding (references the pushed image)
cd deploy/terraform && terraform apply && cd ../..
```

## Verify (round-trip — read live, don't trust "deployed")

```bash
set -a; source .env; set +a
URL=$(gcloud run services describe vcl-wrapper --region "$VCL_LOCATION" \
      --project "$VCL_PROJECT" --format="value(status.url)")
echo "service URL: $URL"

# 1. running?
gcloud run services describe vcl-wrapper --region "$VCL_LOCATION" --project "$VCL_PROJECT" \
  --format="value(status.conditions[0].type, status.conditions[0].status)"

# 2. authenticated lookup_context — VERIFIED DP returns real context, UNVERIFIED withholds.
#    The bearer is a Cloud Run ID TOKEN (audience = service URL); the wrapper itself uses
#    its own SA/ADC for Dataplex, so this token is only Cloud Run's auth gate.
IDTOK=$(gcloud auth print-identity-token)
curl -s -X POST "$URL/mcp" -H "Authorization: Bearer $IDTOK" \
  -H "content-type: application/json" \
  -d "{\"method\":\"tools/call\",\"params\":{\"name\":\"lookup_context\",\"arguments\":{\"projectId\":\"$VCL_PROJECT\",\"location\":\"$VCL_LOCATION\",\"resources\":[\"$VCL_DP_RESOURCE\"]}},\"jsonrpc\":\"2.0\",\"id\":1}"
```

## Point the agent at the deployed wrapper
```
VCL_WRAPPER_URL=<service URL>/mcp        # instead of http://127.0.0.1:8080/mcp
VCL_TOKEN=$(gcloud auth print-identity-token)   # Cloud Run ID token for the auth gate
```
The agent's `McpToolset` sends `Authorization: Bearer $VCL_TOKEN`; Cloud Run validates it
(the caller needs `roles/run.invoker`) and the wrapper serves using its own SA.

## Teardown
```bash
cd deploy/terraform && terraform destroy   # removes service, SA, IAM, AR repo
# APIs left enabled (disable_on_destroy=false).
```
