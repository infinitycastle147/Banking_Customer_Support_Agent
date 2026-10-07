# Agent instructions

Apply these project and personal working rules when changing this repository.

## Code style

- Use meaningful, descriptive file and folder names. Keep each kind of file on one consistent naming convention; use `snake_case` for Python modules.
- Keep comments concise and explain non-obvious reasons, not behavior that the code already makes clear. Prefer a small inline clarification or section heading. If a long explanation seems necessary, first simplify the code; place genuinely useful extended context in Markdown documentation.
- Prefer a single-line docstring. Omit docstrings for self-explanatory functions and fields. Avoid multi-line parameter or field explanations unless a public API or ecosystem convention requires them.
- Do not repeat an identifier or literal in a comment when it is visible in the adjacent code. Put a shared documentation pointer once at the relevant section or module instead of repeating it across related docstrings.
- Mark genuine unfinished work with the exact prefix `TODO: `. Do not add TODOs as a habit.
- Put constants and configuration values in the project's settings/configuration mechanism; do not hardcode secrets or configuration.
- Use filterable dotted event names for structlog calls, such as `search_chunks.completed` or `archive.failed`. Do not add bracketed prefixes.
- Follow the repository's existing structure when adding files. Inspect the current layout before choosing a location.
- Keep shared types, dataclasses, and Pydantic models separate from the implementation that uses them. Give single-use types their own file too.

## Engineering process

- Review and simplify the first working version. Avoid one-use abstractions and repeated computation when an existing result can be reused.
- Never bypass a failing lint check, test, or pre-commit hook to force a change through. Report failures, including unrelated failures, clearly.
- Run tests, the app, and dependency experiments in `uv` or the project's `.venv`; do not install packages directly on the system.
- Flag any proposed new package and explain why it is needed before adding it.
- Report unrelated problems noticed while working. Do not fix them without being asked.

## Version control

- Do not commit or push unless explicitly asked.
- Before a meaningful commit or merge, remind the user to run the `personal-standards-review` and `code-review` skills if they have not already reviewed the change.
- Use a short commit subject prefixed with `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, or `perf`. Use bullets rather than a paragraph for any additional commit detail.

## Communication and judgment

- Be concise, direct, and high-level first. Prefer compact tables or lists over long prose; use no emojis.
- Keep written documentation concise. Keep the README minimal and its structure section current.
- Evaluate proposed approaches critically. Surface meaningful alternatives, edge cases, and trade-offs. If a materially better but more costly approach exists, describe both options and recommend one.
