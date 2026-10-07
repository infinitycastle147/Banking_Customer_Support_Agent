# Banking customer support voice pilot

Local browser pilot for public, source-grounded guidance. It has no customer verification, account access, dispute actions, staff routing, or production bank manual configured. See [the project plan](docs/project_plan.md) and [implementation plan](docs/implementation_plan.md) for the release boundary.

## Run locally

Requires Python 3.13, `uv`, Node.js, and a Gemini API key. The voice pipeline sends live speech to the configured provider. Do not use real customer data.

1. Provide `GEMINI_API_KEY` in an untracked env file. A reference project's env file can be passed directly to `uv run --env-file` without copying its contents into this repository.
2. Run `uv sync` and `uv run --env-file /path/to/your/.env python -m banking_agent.voice.bot`.
3. In `frontend/`, run `npm ci` and `npm run dev`, then open the local URL printed by Vite.

`APPROVED_MANUAL_INDEX` is optional. If absent, all policy searches return unavailable. An index must contain only bank-approved public documents with `document_id`, `version`, `approval_status`, `classification`, `effective_date`, optional `expires_on`, and `sections` containing `section`, `keywords`, and bounded `text`. No sample is loaded by default.

For a local synthetic answer, set `APPROVED_MANUAL_INDEX=tests/fixtures/synthetic_manual_index.json` and ask about support hours. The fixture describes a fictional bank and must not be used as real bank policy.

## Checks

Run `uv run pytest`, `uv run ruff check .`, and `npm run build` in `frontend/`.

## Structure

- `banking_agent/config/`: provider and index settings.
- `banking_agent/knowledge/`: approved public passage lookup.
- `banking_agent/models/`: source and result types.
- `banking_agent/voice/`: Pipecat browser voice pipeline and public tool.
- `frontend/`: local browser client.
- `tests/`: guidance boundary tests.
