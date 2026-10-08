import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request

from banking_agent.banking.demo_store import DemoStore
from banking_agent.banking.transactions import TransactionReader
from banking_agent.config.settings import (
    DEFAULT_DEMO_DB_PATH,
    TRANSACTION_READ_SCOPE,
    VERIFICATION_MAX_AGE,
)
from banking_agent.identity.clerk_auth import ClerkAuthenticator
from banking_agent.models.clerk_identity import ClerkIdentity
from banking_agent.models.record_unavailable import RecordUnavailable
from banking_agent.models.transaction_view import TransactionView
from banking_agent.models.verification_context import VerificationContext


def _view_data(view: TransactionView) -> dict:
    return {
        "reference": view.masked_transaction_id,
        "account": view.masked_account,
        "merchant": view.merchant,
        "amount": str(view.amount),
        "currency": view.currency,
        "status": view.status,
        "occurred_at": view.occurred_at.isoformat(),
        "description": view.bank_description,
    }


def create_app(
    *, authenticator: ClerkAuthenticator | None = None, store: DemoStore | None = None
) -> FastAPI:
    authenticator = authenticator or ClerkAuthenticator()
    store = store or DemoStore(
        Path(os.getenv("DEMO_DB_PATH", str(DEFAULT_DEMO_DB_PATH)))
    )
    app = FastAPI(title="Harbor support API")

    @app.middleware("http")
    async def prevent_caching(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def identity(
        authorization: Annotated[str | None, Header()] = None,
    ) -> ClerkIdentity:
        verified = authenticator.authenticate(authorization)
        if verified is None:
            raise HTTPException(status_code=401, detail="Sign in is required.")
        return verified

    def context_for(verified: ClerkIdentity) -> VerificationContext:
        now = datetime.now(UTC)
        if verified.expires_at <= now:
            raise HTTPException(status_code=401, detail="Sign in is required.")
        return VerificationContext(
            session_id=verified.session_id,
            customer_id=verified.user_id,
            verification_reference=verified.session_id,
            method="clerk-session",
            permitted_actions=frozenset({TRANSACTION_READ_SCOPE}),
            verified_at=now,
            expires_at=min(now + VERIFICATION_MAX_AGE, verified.expires_at),
        )

    @app.get("/api/transactions")
    def list_transactions(
        verified: Annotated[ClerkIdentity, Depends(identity)],
    ) -> dict:
        context = context_for(verified)
        store.ensure_customer(verified.user_id)
        records = TransactionReader(store.transactions(verified.user_id))
        views = records.list_customer_transactions(
            context, session_id=verified.session_id
        )
        return {"transactions": [_view_data(view) for view in views]}

    @app.get("/api/transactions/{reference_suffix}")
    def get_transaction(
        reference_suffix: str, verified: Annotated[ClerkIdentity, Depends(identity)]
    ) -> dict:
        if len(reference_suffix) != 4 or not reference_suffix.isdigit():
            raise HTTPException(status_code=404, detail="Transaction unavailable.")
        context = context_for(verified)
        owned = store.transactions(verified.user_id)
        matches = [
            record
            for record in owned
            if record.transaction_id.endswith(reference_suffix)
        ]
        if len(matches) != 1:
            raise HTTPException(status_code=404, detail="Transaction unavailable.")
        records = TransactionReader(owned)
        try:
            view = records.get_transaction(
                matches[0].transaction_id, context, session_id=verified.session_id
            )
        except RecordUnavailable:
            raise HTTPException(
                status_code=404, detail="Transaction unavailable."
            ) from None
        return {"transaction": _view_data(view)}

    @app.post("/api/voice-tickets")
    def create_voice_ticket(
        verified: Annotated[ClerkIdentity, Depends(identity)],
    ) -> dict:
        context_for(verified)
        store.ensure_customer(verified.user_id)
        return {"ticket": store.create_voice_ticket(verified)}

    return app


app = create_app()
