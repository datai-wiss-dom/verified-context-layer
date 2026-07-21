#!/usr/bin/env python3
"""
Lesson MD Converter — Udacity ADK Course 2
Converts raw text into compressed .claude/current/ markdown files.
Uses Vertex AI Gemini via ADC — no API key needed.

Setup (one time):
uv add google-genai
gcloud auth application-default login
gcloud config set project agentic-2026-493108

Usage:
python manageskills/ai_md_converter.py --type lesson --lesson L1
python manageskills/ai_md_converter.py --type exercise --lesson L1
python manageskills/ai_md_converter.py --type plan --lesson L1
python manageskills/ai_md_converter.py                     # interactive mode
python manageskills/ai_md_converter.py --type lesson        # direct type
python manageskills/ai_md_converter.py--type exercise
python manageskills/ai_md_converter.py --type plan
python manageskills/ai_md_converter.py--lesson L10         # set lesson number
python manageskills/ai_md_converter.py --input notes.txt    # read from file

Author: Wissem Khlifi
Date: 04/2026
"""

import re
import sys
import argparse
import textwrap
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
GCP_PROJECT  = "agentic-2026-493108"
GCP_LOCATION = "us-central1"
GEMINI_MODEL = "gemini-2.5-flash"

# Token limits per file type — generous to avoid truncation

MAX_TOKENS = {
    "lesson":   4096,
    "exercise": 2048,
    "plan":     4096,   # plans can be long with code blocks
}

# ── Dependency check ──────────────────────────────────────────────────────────

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai not found.")
    print("Run:  uv add google-genai")
    sys.exit(1)

# ── System prompts per file type ──────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "lesson": """
You convert raw Udacity lesson notes into a compressed lesson.md for Claude Code context.

OUTPUT FORMAT - use exactly this structure with proper markdown:

# {lesson} - [Lesson Title]: Key Concepts

## What [topic] is in ADK

2-3 sentences max, precise, no padding.

## Core ADK classes for this lesson

- `ClassName` - one-line purpose
- `ClassName` - one-line purpose

## Key decisions for my implementation

- **Decision**: explanation
- **Decision**: explanation

## Gaps / questions from lesson

- question or gap noted during study

RULES:

- Use **bold** for emphasis on key terms
- Use backticks for all class/method/variable names
- Use proper bullet points with dash character
- Blank line between every section
- Be ruthlessly compressed, no restating what ADK already knows
- Focus on DECISIONS and GAPS not textbook definitions
- Output ONLY the markdown, no wrapping code fences, no preamble, no explanation
- Never truncate - always complete every section fully
""",

    "exercise": """
You convert raw Udacity exercise requirements into a compressed exercise.md for Claude Code context.

OUTPUT FORMAT - use exactly this structure with proper markdown:

# {lesson} Exercise Requirements

## Goal

1-2 sentences: what is being built in this exercise.

## Deliverables

- [ ] specific checkable item
- [ ] specific checkable item

## Acceptance criteria

- exact requirement from Udacity
- exact requirement from Udacity

## Out of scope

- what NOT to build in this lesson

RULES:

- Use **bold** for critical requirements
- Use backticks for ADK class and method names
- Use - [ ] checkbox format for all deliverables
- Blank line between every section
- Deliverables must be specific and checkable not vague
- Mark anything unclear as TODO:
- Output ONLY the markdown, no wrapping code fences, no preamble, no explanation
- Never truncate - always complete every section fully
""",

    "plan": """
You convert rough implementation notes into a complete plan.md for Claude Code context.

OUTPUT FORMAT - use exactly this structure with proper markdown:

# {lesson} Implementation Plan

## Step 1: [Name]

Clear description of what to do.

```bash
actual-command --with-flags here
```

## Step 2: [Name]

Clear description of what to do.

```python
# code snippet if relevant
```

## Status

- [ ] Step 1: [Name]
- [ ] Step 2: [Name]
- [ ] Step 3: [Name]

RULES:

- Use **bold** for important warnings or notes
- Use backticks for class/method names inline
- Use bash or python code blocks for all commands and snippets
- Blank line between every step
- Steps must be ordered and immediately actionable
- Include actual shell commands: agents-cli, uv, gcloud where relevant
- If input has no clear steps, infer sensible ones from context
- Output ONLY the markdown, no wrapping code fences around the whole doc, no preamble
- Never truncate - always complete every step and the status section fully
""",
}

# ── Converter ─────────────────────────────────────────────────────────────────

def convert_to_md(raw_text: str, file_type: str, lesson: str) -> str:
    """Call Vertex AI Gemini via ADC using new google-genai SDK."""
    print(f"\n  Initialising Vertex AI ({GCP_PROJECT} / {GCP_LOCATION})...")

    # New SDK — uses ADC automatically, no deprecated GenerativeModel
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=GCP_LOCATION,
    )

    system = SYSTEM_PROMPTS[file_type].replace("{lesson}", lesson)
    max_tok = MAX_TOKENS[file_type]

    print(f"  Calling {GEMINI_MODEL} (max_tokens={max_tok})...")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=raw_text,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tok,
            temperature=0.2,
        ),
    )

    # Check finish reason — warn if still truncated
    candidate = response.candidates[0]
    finish = candidate.finish_reason.name if candidate.finish_reason else "UNKNOWN"
    if finish == "MAX_TOKENS":
        print(f"\n  WARNING: Output hit token limit ({max_tok}).")
        print("  Consider splitting your input into smaller chunks.")
    else:
        print(f"  Finish reason: {finish}")

    return response.text

def archive_current_lesson(lesson: str) -> bool:
    """Move .claude/current/ files to docs/archive/ before writing new lesson."""
    current_dir = PROJECT_ROOT / ".claude" / "current"
    archive_dir = PROJECT_ROOT / "docs" / "archive"

    if not current_dir.exists():
        return False

    files = list(current_dir.glob("*.md"))
    if not files:
        print("  Nothing to archive in .claude/current/")
        return False

    archive_dir.mkdir(parents=True, exist_ok=True)

    # Read current lesson prefix from CLAUDE.md
    claude_md = PROJECT_ROOT / "CLAUDE.md"
    prefix = "old"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        match = re.search(r"- Lesson:\s*(L\d+)", content)
        if match:
            prefix = match.group(1)

    for f in files:
        dst = archive_dir / f"{prefix}_{f.name}"
        f.rename(dst)
        print(f"  Archived          -> docs/archive/{prefix}_{f.name}")
        # Remove HANDOFF.md if exists — stale after lesson advance
        handoff = PROJECT_ROOT / "HANDOFF.md"
        if handoff.exists():
            handoff.unlink()
            print(f"  Removed           -> HANDOFF.md (stale)")
        return True

# ── Save helpers ──────────────────────────────────────────────────────────────
def save_to_current(md: str, file_type: str) -> "Path | None":
    """Save to .claude/current/ if it exists in cwd."""
    current_dir = PROJECT_ROOT / ".claude" / "current"
    if current_dir.exists():
        out_path = current_dir / f"{file_type}.md"
        out_path.write_text(md, encoding="utf-8")
        return out_path
    return None

def update_lesson_in_file(path: Path, lesson: str, title: str = "") -> bool:
    """Replace lesson reference in CLAUDE.md or GEMINI.md."""
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    # Matches lines like: - Lesson: L9 or - Lesson: L9 - Some Title
    repl = r"\1" + lesson + (f" - {title}" if title else "")
    updated = re.sub(
        r"(- Lesson:\s*)L\d+.*",
        repl,
        content,
    )
    if updated != content:
        path.write_text(updated, encoding="utf-8")
        return True
    return False

def update_course_map(lesson: str) -> bool:
    """Mark previous lesson done in docs/reference/course-map.md."""
    path = PROJECT_ROOT / "docs" / "reference" / "course-map.md"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    prev_num = int(lesson[1:]) - 1
    if prev_num < 1:
        return False
    prev = f"L{prev_num}"
    updated = re.sub(
        rf"(- {prev}\s+.+?)(?<!\s✓)$",
        r"\1  ✓",
        content,
        flags=re.MULTILINE,
    )
    # Remove old CURRENT marker, then set new one
    updated = re.sub(r"\s*<– CURRENT", "", updated)
    updated = re.sub(
        rf"(- {lesson}\s+.+?)$",
        r"\1  <– CURRENT",
        updated,
        flags=re.MULTILINE,
    )
    if updated != content:
        path.write_text(updated, encoding="utf-8")
        return True
    return False

# ── Input helpers ─────────────────────────────────────────────────────────────

def get_raw_input_interactive(file_type: str) -> str:
    """Collect multi-line input from terminal."""
    print(f"\n  Paste your raw {file_type} text below.")
    print("  When done, type END on a new line and press Enter:\n")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)

# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert raw text to .claude/current/ markdown via Vertex AI Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
Examples:
python md_converter.py
python md_converter.py --type lesson --lesson L10
python md_converter.py --type exercise --input raw_exercise.txt
python md_converter.py --type plan --lesson L10 --input notes.txt
""")
    )
    parser.add_argument(
        "--type", "-t",
        choices=["lesson", "exercise", "plan"],
        help="Type of MD file to generate",
    )
    parser.add_argument(
        "--lesson", "-l",
        default=None,
        help="Lesson identifier e.g. L9, L10 (default: prompt user)",
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="Path to input text file (default: interactive terminal input)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 55)
    print("  Lesson MD Converter")
    print(f"  Model : {GEMINI_MODEL}")
    print("  Auth  : Vertex AI ADC (no API key needed)")
    print("=" * 55)

    # ── File type ──
    file_type = args.type
    if not file_type:
        print("\n  What type of file are you generating?")
        print("  1. lesson.md   - concepts and key decisions")
        print("  2. exercise.md - exercise requirements")
        print("  3. plan.md     - implementation steps")
        choice = input("\n  Enter 1, 2 or 3: ").strip()
        mapping = {"1": "lesson", "2": "exercise", "3": "plan"}
        file_type = mapping.get(choice)
        if not file_type:
            print("  Invalid choice. Exiting.")
            sys.exit(1)

    # ── Lesson number ──
    lesson = args.lesson
    if not lesson:
        lesson = input("\n  Lesson number (e.g. L9, L10) [L9]: ").strip() or "L9"

    # ── Raw input ──
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"  ERROR: File not found: {input_path}")
            sys.exit(1)
        raw_text = input_path.read_text(encoding="utf-8")
        print(f"\n  Read {len(raw_text)} chars from {input_path}")
    else:
        raw_text = get_raw_input_interactive(file_type)

    if not raw_text.strip():
        print("  ERROR: No input provided. Exiting.")
        sys.exit(1)

    # ── Convert ──
    try:
        md = convert_to_md(raw_text, file_type, lesson)
    except Exception as e:
        print(f"\n  ERROR during conversion: {e}")
        print("\n  Troubleshooting:")
        print("  1. gcloud auth application-default login")
        print("  2. gcloud config set project agentic-2026-493108")
        print("  3. uv add google-genai")
        print("  4. Vertex AI API enabled in GCP console")
        sys.exit(1)

    # ── Print output ──
    print("\n" + "-" * 55)
    print(f"  OUTPUT - {lesson} {file_type}.md")
    print("-" * 55 + "\n")
    print(md)
    print("\n" + "-" * 55)

    # ── Archive current lesson if this is a new lesson run ──
    if file_type == "lesson":
        print("\n  Archiving current lesson files...")
        archive_current_lesson(lesson)

    # ── Save to .claude/current/ ──
    saved = save_to_current(md, file_type)

    if saved:
        print(f"  Saved to project  -> {saved}")
    else:
        print("  NOTE: .claude/current/ not found in cwd.")
        print("  Run from your project root to auto-save.")

    # ── Update CLAUDE.md and GEMINI.md ──
    claude_md = PROJECT_ROOT / "CLAUDE.md"
    gemini_md = PROJECT_ROOT / "GEMINI.md"

    if update_lesson_in_file(claude_md, lesson):
        print(f"  Updated lesson    -> CLAUDE.md")
    else:
        print(f"  NOTE: Could not update CLAUDE.md (not found or pattern missing)")

    if update_lesson_in_file(gemini_md, lesson):
        print(f"  Updated lesson    -> GEMINI.md")

    # ── Update course-map.md ──
    if update_course_map(lesson):
        print(f"  Updated course map -> docs/reference/course-map.md")

    # ── Commenting save fallback in cwd ──
    # fallback = Path.cwd() / f"{lesson}_{file_type}.md"
    # fallback.write_text(md, encoding="utf-8")
    # print(f"  Fallback saved    -> {fallback.name}")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
