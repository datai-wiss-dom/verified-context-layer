# VCL BUILD GUIDELINES — how to work on this system


> Read with ARCHITECTURE.md. That document says WHAT must not break; this one says HOW
> to work so you don't break it. These rules exist because specific failures have
> happened on this project. Follow them literally.


---


## §0. PRECEDENCE AND STOPPING (read first)


Order of authority, highest first:
1. **ARCHITECTURE.md §1 INVARIANTS** — never violate, for any reason.
2. **ARCHITECTURE.md** (state model, verified facts, components).
3. **The current phase's task spec** — the specific thing you were asked to do now.
4. **Your own judgment** — lowest. Used only to CHOOSE HOW within the above, never to
   OVERRIDE them.


**The STOP rule (most important rule in this document):**
If a task requires a decision NOT explicitly covered by the above — a design choice, a
tradeoff, a workaround, touching a file the task didn't name, an invariant that seems to
conflict with the task — **STOP. State the decision you face and the options. Wait for a
human answer.** Do NOT decide silently and proceed. A silent reasonable-looking decision
is the most dangerous thing you can do here, because it will not be reviewed.
(Real past examples: an MCP client shim, edits to catalog documentation content — both
reasonable, both should have been flagged before doing, not reported after.)


---


## §1. THE "PROVEN" RULE — evidence discipline


This project's single most common error is reporting work as **"proven"** or "working
end-to-end" when it was only BUILT. Therefore:


- **Never write "proven", "verified", "works", or "tested" without pasting the actual
  terminal output you observed that shows it.** Not "I ran it and it passed" — the
  literal output.
- Distinguish three claims explicitly and never blur them:
  - **"authored"** — I wrote the file. (No runtime claim.)
  - **"ran"** — I executed it; here is the raw output.
  - **"verified"** — I executed it AND round-tripped the result (read the resource back /
    confirmed the observable check), here is that output too.
- If you cannot run something (no credentials, no network, wrong environment), say so
  plainly: "authored, NOT run — the human must run X to verify." Never imply it works.
- A tool's success message, an API 200, a "Terraform apply complete", a docstring — none
  of these are proof. Proof is a clean READ-BACK of the exact resource (ARCHITECTURE
  INV-7). Example: after writing a verdict, read the aspect back and show the value;
  after a Terraform apply, describe the resource and show it exists as intended.


---


## §2. VERIFY EXTERNAL APIS BEFORE USING THEM


APIs age; your training memory of a library is often stale. Before writing code against
any external symbol (ADK class, Terraform resource, gcloud flag, SDK method):
- **Confirm it exists in the INSTALLED version**, with a shown command. Examples:
  - `python3 -c "from X import Y; print('ok')"` for an import.
  - `<cli> <cmd> --help` for a flag/subcommand.
  - the provider registry / `terraform providers schema` for a resource/field.
- ARCHITECTURE §4 lists facts already verified on this project. You MAY rely on them,
  but if the environment/version may have changed, RE-VERIFY and note that you did.
- If a symbol you expected does not exist, STOP (§0) — do not substitute a similar-looking
  one from memory. A plausible-wrong API is worse than an admitted gap.


---


## §3. SMALLEST CORRECT CHANGE


- Make the smallest change that satisfies the task. Do not refactor, rename, reformat, or
  "improve" code the task didn't ask you to touch.
- **One file at a time.** After editing a file, re-verify (syntax check + the relevant
  observable check) BEFORE touching the next. Coordinated multi-file changes (e.g. a
  schema field + the code that writes it + the code that reads it) are done in dependency
  order, verifying each step round-trips before the next. (Past failure: a broad find-
  replace hit an unintended call site; a schema apply was skipped while code assumed it
  applied — both caught only by round-trip.)
- Never widen a change to "while I'm here." If you notice something else wrong, NOTE it,
  don't fix it unasked (§0).


---


## §4. RESPECT THE TRUST AND PLANE BOUNDARIES (ARCHITECTURE §1, §3)


- Do not add an AI import to `src/vcl.py` (INV-1). If a task seems to need AI in the
  verifier, STOP — it belongs in the triage, not the core.
- Do not make the wrapper or triage WRITE the verdict (INV-2, INV-3).
- Do not put enforcement in an agent prompt (INV-4). Enforcement is tool code reading the
  verdict.
- Do not create a `source_tier` state that keeps serving (INV-5).
- Do not modify the wrapper to satisfy a strict MCP client — accommodate on the client
  side (ARCHITECTURE §4, the lookup_context output-schema note).
- Do not attempt to Terraform aspect CONTENT (ARCHITECTURE §4 — provider doesn't support
  it; it is script/vcl.py territory).


---


## §5. KNOWLEDGE-CATALOG-SPECIFIC CARE


- Use project NUMBER (not id) in aspect keys / `@spanner` paths where ARCHITECTURE §4
  says so.
- datetime aspect fields: OMIT to clear, never `""` (400). String fields accept `""`.
- Never fingerprint a `None`/absent timestamp from a DQ scan; prefer endTime → createTime
  → skip.
- After ANY write to the catalog, READ IT BACK (CUSTOM view) and show the stored value.
  `@dataplex` DP-path writes persist; do not assume other paths do.


---


## §6. SECRETS AND IDENTIFIERS


- Never hardcode project id/number, emails, or tokens in committed files. Read from env
  (`.env`, gitignored) with placeholder defaults.
- Before reporting a phase done, run the leak check and show it returns clean:
  `git grep -nE "<real-project-number>|<real-project-id>|<owner-email>" -- '*.py' '*.md' '*.tf'`
- `.env` gitignored; `.env.example` committed with placeholders only.


---


## §7. PHASES AND HANDOFF


- Work one PHASE at a time (schema → scripts → terraform → tests are separate phases with
  dependencies; a later phase may assume an earlier one is verified — confirm it is).
- At the end of a phase, report in this exact shape:
  1. **Changed:** the files you touched (and nothing else).
  2. **Authored / Ran / Verified:** which claim applies to each piece, with the terminal
     output for anything you call "ran" or "verified" (§1).
  3. **Decisions flagged:** anything you STOPPED on, or any assumption you had to make.
  4. **Not done / needs human:** what you could not verify and the exact command the
     human should run to verify it.
  5. **Invariant checks:** paste the results of the relevant ARCHITECTURE §1 CHECK
     commands, showing they still pass.
- If you must stop mid-phase (quota, blocker), write what is done, what is verified, and
  the exact next step, so the next session resumes without re-deriving.


---


## §8. THE ONE-LINE SPIRIT


You are the HANDS. The human is the architect and the verifier. Your job is to execute
precisely, verify empirically, and surface decisions — not to make architectural choices
silently or to declare victory unproven. When unsure: do less, show more, ask.
