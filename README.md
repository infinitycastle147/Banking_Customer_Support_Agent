# Harbor Support

Browser voice support with Clerk sign-in, customer-scoped sample transaction activity, and source-grounded public guidance. The activity is generated for demonstration and is not connected to a bank. Dispute submission and real account access are not available.

## Run locally

Requires Python 3.13, `uv`, Node.js, a Gemini API key, and Clerk publishable and secret keys from the same Clerk application.

1. Copy `.env.example` to `.env`. Set `GEMINI_API_KEY`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, and `CLERK_SECRET_KEY`. Set `CLERK_AUTHORIZED_PARTIES` to the exact browser origin you use, such as `http://127.0.0.1:5173`. Keep `.env` untracked.
2. Run `UV_CACHE_DIR=/private/tmp/banking-agent-uv-cache uv sync`.
3. Start the API: `uv run --env-file .env uvicorn banking_agent.banking.api:app --host 127.0.0.1 --port 8000`.
4. Start the voice runner in another terminal: `uv run --env-file .env python -m banking_agent.voice.bot`.
5. In `frontend/`, run `npm ci` and `npm run dev`, then open the Vite URL. Vite reads the root `.env` and exposes the Clerk publishable key, but not the secret, to the browser.

The browser sends a Clerk session token only to the API. The API verifies it, creates records scoped to that Clerk user, and issues a one-use voice ticket valid for up to 30 seconds. The voice runner redeems the ticket and checks the resulting read scope, valid for up to five minutes, before speaking any transaction details. API lookups also check customer ownership. Never use real customer data in this demo.

The configured `APPROVED_MANUAL_INDEX` points to a test handbook. It covers basic cheque guidance and directs support-hours questions to the bank's official channel; its approval metadata is only for testing. Replace it with bank-reviewed public documents before using the guidance for a real bank. The voice system speaks only retrieved passages and fixed responses.

## Checks

Run `uv run pytest`, `uv run ruff check .`, and `npm run build` in `frontend/`.

## Structure

- `banking_agent/banking/`: scoped transaction reads, sample record store, and authenticated API.
- `banking_agent/identity/`: Clerk session verification and read authorization.
- `banking_agent/knowledge/`: public document ingestion and lookup.
- `banking_agent/voice/`: Pipecat browser voice pipeline and typed tools.
- `banking_agent/disputes/`, `banking_agent/cases/`, `banking_agent/audit/`, `migrations/`: local dispute workflow and staff artifacts, not connected to the browser.
- `banking_agent/models/`: shared data types.
- `frontend/`: Clerk sign-in, sample activity, and voice client.
- `tests/`: service and access-boundary tests.
