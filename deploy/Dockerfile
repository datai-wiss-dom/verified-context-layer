# Slim container for the VCL wrapper. No gcloud — the wrapper authenticates to Dataplex
# via the runtime service account's ADC (google-auth). Config comes from Cloud Run env
# vars (VCL_PROJECT / VCL_LOCATION / VCL_ASPECT_TYPE); no .env, no VCL_TOKEN in the image.
FROM python:3.13-slim

WORKDIR /app

COPY deploy/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# The wrapper source, unchanged in behaviour (gating logic untouched). It binds 0.0.0.0:$PORT.
COPY src/vcl_wrapper.py /app/src/vcl_wrapper.py

# Cloud Run injects PORT; the wrapper reads it and binds 0.0.0.0.
CMD ["python", "/app/src/vcl_wrapper.py"]
