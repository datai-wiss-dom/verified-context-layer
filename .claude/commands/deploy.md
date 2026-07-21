---
name: deploy
description: Deploy current ADK agent to Cloud Run on GCP
---

## Deploy Agent to Cloud Run
1. Verify GCP auth
   ```
   gcloud auth application-default login
   ```
2. Deploy
   ```
   agents-cli deploy
   ```
