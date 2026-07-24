# Author: Wissem Khlifi · July 2026
# The `verification` aspect-type SCHEMA (shape only). The VALUES (source_tier, anchors,
# certified_text, ...) are written later by `vcl.py seal` at runtime — that is the dynamic,
# verified state Terraform deliberately does not own. Schema comes from the committed v8
# template so it stays in lockstep with what vcl.py / the wrapper read/write.

resource "google_dataplex_aspect_type" "verification" {
  aspect_type_id = "verification"
  project        = var.project_id
  location       = var.location

  metadata_template = file("${path.module}/../../schemas/verification_v8_certtext.json")

  depends_on = [time_sleep.api_propagation]
}
