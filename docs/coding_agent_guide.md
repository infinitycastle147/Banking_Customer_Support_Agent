# Coding agent guide

Use this file with [the product plan](project_plan.md) and [the implementation plan](implementation_plan.md). Read the repository [AGENTS.md](../AGENTS.md) first; it governs code style, testing, dependencies, and version control. The product plan defines behavior and security boundaries. The implementation plan defines the proposed build order and reference files. If a design decision conflicts with either plan, surface it before silently changing the contract.

## How to take a work item

1. Identify its milestone and acceptance gate in the implementation plan. State the smallest useful end-to-end slice and the files it will touch. Inspect the current repository and nearby tests before editing.
2. Check the linked reference projects for patterns, then check the locked dependency version and current documentation for APIs you will use. For library/API questions, resolve the library in Context7 before querying its docs; use official documentation if Context7 is unavailable. Never send secrets, customer data, or proprietary code in documentation queries. Treat reference code as evidence, not as project policy. If copying is warranted, check ownership/licensing and refactor to this repository's `AGENTS.md` rules.
3. Keep a clear boundary: Pipecat handles speech and tool invocation; application services own identity, authorization, records, command validation, and human review. No model-generated SQL or direct model database/queue credentials.
4. Implement with synthetic customers, transactions, disputes, and approved sample manuals until a bank integration is explicitly selected. Never put real customer data, OTPs, or secrets in fixtures, telemetry, or documentation. Send only the minimum authorized content needed to the model and avoid retaining raw transcripts by default.
5. Run focused tests in `uv` or `.venv`, then the available lint, full test, and frontend build checks. Review and simplify the first working version. Report the exact commands and outcomes; do not bypass a failure.

## Security invariants to preserve in every slice

- Public manual lookup may be unauthenticated. Every customer, transaction, dispute, request-status, or case operation needs a verified and scoped session; the service rechecks ownership for each target record. A voice utterance, caller ID, account number, or model assertion never supplies identity.
- Readback and explicit customer consent precede a dispute write request. The command API validates a typed payload and returns a request ID only after durable acceptance. An `accepted` request is not an approved dispute.
- Retries reuse one server-generated idempotency key. The agent checks status after an unknown outcome; it does not issue a fresh command. Workers withstand replay, concurrent updates, process restart, and stale versions. Withdrawal retains history.
- Denials and errors are structured and safe to speak. A failed authorization must not reveal whether another customer's record exists. Rate limits and duplicate detection are enforced by the service, not by a prompt alone.
- Retrieved manuals, transaction descriptors, and transcripts are untrusted inputs. Bank policy and tool permissions are code-enforced. Logs and staff notifications contain only approved, masked fields.
- No background LLM agent or knowledge graph is required. The dispute worker is ordinary durable application code, not an autonomous decision maker. A human controls final dispute outcomes.

## What can proceed now

| Can build with synthetic data | Needs a bank decision before real integration |
| --- | --- |
| Pipecat browser pilot; approved-document ingestion prototype; source-grounded answers; typed tool contracts; verification and bank adapter interfaces; dispute state machine; outbox worker; security and concurrency tests. | Bank/jurisdiction and authoritative manuals; identity provider; transaction/dispute/case APIs; consent and retention policy; escalation thresholds; notification destination; voice channel, languages, and approved model providers. |

Keep provider-specific behavior behind narrow adapters. Do not invent production values for unresolved choices or make a mock verification result usable outside tests and local development.

## Definition of done for a coding slice

- The observable behavior matches its plan acceptance gate, including denied, duplicate, timeout, interruption, and unavailable-system cases relevant to that slice.
- Tests cover the service boundary and a meaningful failure path. For write flows, include replay and concurrent-request checks; for guidance, include missing/conflicting source checks; for identity, include cross-customer denial.
- New dependencies and configuration are documented and locked; settings contain thresholds, endpoints, models, and secrets references. No secrets or customer data appear in a diff.
- Audit and metric events are redacted, use dotted names, and can be correlated by request ID without retaining unnecessary conversation text.
- The first implementation has been reviewed for unnecessary abstractions and repeated work. The coding agent reports changed files, test results, remaining risks, and any product or bank decision that prevents a production integration.

Do not commit or push unless explicitly asked. Before a meaningful commit or merge, follow the review instructions in `AGENTS.md`.
