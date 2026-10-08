import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from banking_agent.banking.api import create_app
from banking_agent.banking.demo_store import DemoStore
from banking_agent.models.clerk_identity import ClerkIdentity
from banking_agent.voice.tools import build_transaction_tool


class FakeAuthenticator:
    def authenticate(self, authorization):
        if authorization not in ("Bearer alice", "Bearer bob"):
            return None
        user_id = authorization.removeprefix("Bearer ")
        return ClerkIdentity(
            user_id=user_id,
            session_id=f"session-{user_id}",
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )


def test_authentication_is_required_and_records_are_customer_scoped(tmp_path):
    client = TestClient(
        create_app(
            authenticator=FakeAuthenticator(),
            store=DemoStore(tmp_path / "demo.sqlite3"),
        )
    )
    denied = client.get("/api/transactions")
    assert denied.status_code == 401
    assert denied.headers["Cache-Control"] == "no-store"
    assert client.post("/api/voice-tickets").status_code == 401

    alice = client.get(
        "/api/transactions", headers={"Authorization": "Bearer alice"}
    ).json()["transactions"]
    bob = client.get(
        "/api/transactions", headers={"Authorization": "Bearer bob"}
    ).json()["transactions"]
    assert len(alice) == len(bob) == 8
    assert {item["reference"] for item in alice}.isdisjoint(
        {item["reference"] for item in bob}
    )
    suffix = alice[0]["reference"][-4:]
    assert (
        client.get(
            f"/api/transactions/{suffix}",
            headers={"Authorization": "Bearer alice"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/transactions/{suffix}",
            headers={"Authorization": "Bearer bob"},
        ).status_code
        == 404
    )


def test_voice_ticket_is_one_use_and_bound_to_signed_in_customer(tmp_path):
    store = DemoStore(tmp_path / "demo.sqlite3")
    client = TestClient(create_app(authenticator=FakeAuthenticator(), store=store))
    ticket = client.post(
        "/api/voice-tickets", headers={"Authorization": "Bearer alice"}
    ).json()["ticket"]

    context = store.redeem_voice_ticket(ticket)

    assert context.customer_id == "alice"
    assert context.verification_reference == "session-alice"
    assert store.redeem_voice_ticket(ticket) is None
    assert store.redeem_voice_ticket("unknown") is None


def test_expired_ticket_is_rejected(tmp_path):
    store = DemoStore(tmp_path / "demo.sqlite3")
    identity = ClerkIdentity(
        "alice", "session-alice", datetime.now(UTC) - timedelta(seconds=1)
    )
    ticket = store.create_voice_ticket(identity)

    assert store.redeem_voice_ticket(ticket) is None


def test_voice_tool_reads_only_ticket_customer_activity(tmp_path):
    store = DemoStore(tmp_path / "demo.sqlite3")
    client = TestClient(create_app(authenticator=FakeAuthenticator(), store=store))
    ticket = client.post(
        "/api/voice-tickets", headers={"Authorization": "Bearer alice"}
    ).json()["ticket"]
    context = store.redeem_voice_ticket(ticket)
    bob_references = [
        item["reference"][-4:]
        for item in client.get(
            "/api/transactions", headers={"Authorization": "Bearer bob"}
        ).json()["transactions"]
    ]

    class Call:
        def __init__(self):
            self.arguments = {}
            self.spoken = []
            self.llm = self
            self.result = None

        async def push_frame(self, frame):
            self.spoken.append(frame.text)

        async def result_callback(self, result, *, properties):
            self.result = result

    call = Call()
    asyncio.run(build_transaction_tool(store, context).handler(call))

    assert call.result == {"status": "found"}
    assert "Greenfield Grocers" in call.spoken[0]
    assert all(
        f"reference ending {suffix}" not in call.spoken[0] for suffix in bob_references
    )

    alice_reference = store.transactions("alice")[0].transaction_id[-4:]
    detail_call = Call()
    detail_call.arguments = {"last_four": alice_reference}
    asyncio.run(build_transaction_tool(store, context).handler(detail_call))
    assert "recorded description" in detail_call.spoken[0]
    assert f"ending {alice_reference}" in detail_call.spoken[0]

    expired = replace(context, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    expired_call = Call()
    asyncio.run(build_transaction_tool(store, expired).handler(expired_call))
    assert expired_call.result == {"status": "verification_required"}
