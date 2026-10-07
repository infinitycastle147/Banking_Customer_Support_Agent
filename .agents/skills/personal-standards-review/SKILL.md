---
name: personal-standards-review
description: Review the current diff, branch, PR, or specified code against the personal working standards in this repository's AGENTS.md. Use when asked for a personal standards review.
---

# Personal standards review

Review the requested target against this repository's `AGENTS.md` and any other applicable repository instructions. Read the current instructions before reviewing; do not rely on remembered rules. If the target is not specified, ask which diff, branch, PR, or files to review.

Report only genuine violations. Do not manufacture findings to fill the report.

## Checklist

### Code style

- Names are descriptive and file/folder names follow the conventions used for their kind in this repository.
- Comments explain non-obvious reasons, stay concise, and do not narrate visible code or developer thought process.
- Docstrings are omitted when names and signatures are self-explanatory; otherwise they are concise and use one line where practical. Multi-line documentation is used only when the public API or ecosystem requires it.
- Comments do not repeat identifiers or literals visible in adjacent code. Shared documentation pointers are not repeated across related docstrings.
- Genuine unfinished work uses the exact `TODO: ` prefix.
- Constants and configuration use the project's configuration mechanism; secrets and configuration are not hardcoded.
- structlog event names are dotted and filterable (for example, `search_chunks.completed`), without bracketed prefixes.
- New files follow the existing repository structure.
- Types, dataclasses, and Pydantic models are kept separate from implementation files.

### Engineering process

- The implementation has been reviewed and simplified; there are no unnecessary one-use abstractions or repeated computations where a result could be reused.
- No lint check, test, or pre-commit hook was bypassed.
- New packages are flagged with their purpose rather than added silently.
- Out-of-scope problems noticed during the work were reported and not changed unprompted.

### Version control

- No commit or push occurred without explicit authorization.
- Commit subjects use an allowed prefix and are concise; additional details use bullets.

## Output

Start with a compact table of category and status. Expand only categories with actual issues. If all categories are clean, report `PASS — no violations found` and stop.
