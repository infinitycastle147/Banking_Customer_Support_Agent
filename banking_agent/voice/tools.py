from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import FunctionCallResultProperties, TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams

from banking_agent.banking.demo_store import DemoStore
from banking_agent.banking.transactions import TransactionReader
from banking_agent.config.settings import TRANSACTION_READ_SCOPE
from banking_agent.identity.verification import require_verified_session
from banking_agent.knowledge.retrieval import search_approved_manual
from banking_agent.models.access_denied import AccessDenied
from banking_agent.models.manual_passage import ManualPassage
from banking_agent.models.verification_context import VerificationContext


def build_greeting_tool() -> FunctionSchema:
    async def greet(params: FunctionCallParams) -> None:
        await params.llm.push_frame(TTSSpeakFrame("Hello. How can I help?"))
        await params.result_callback(
            {"status": "greeted"},
            properties=FunctionCallResultProperties(run_llm=False),
        )

    return FunctionSchema(
        name="greet_customer",
        description="Give a brief greeting when the customer only says hello.",
        properties={},
        required=[],
        handler=greet,
    )


def build_public_guidance_tool(passages: tuple[ManualPassage, ...]) -> FunctionSchema:
    async def lookup(params: FunctionCallParams) -> None:
        query = (params.arguments or {}).get("query", "")
        result = search_approved_manual(query, passages)
        if result.status == "found":
            passage = result.passages[0]
            spoken = (
                f"{passage.text} Source: {passage.reference.document_id}, "
                f"version {passage.reference.version}, section {passage.reference.section}."
            )
        else:
            spoken = "Approved guidance is unavailable for that question. Please contact bank staff."
        await params.llm.push_frame(TTSSpeakFrame(spoken))
        await params.result_callback(
            {"status": result.status},
            properties=FunctionCallResultProperties(run_llm=False),
        )

    return FunctionSchema(
        name="search_approved_manual",
        description="Speak an exact approved public guidance passage with its source, or an unavailable message. Call this for every public guidance question.",
        properties={
            "query": {
                "type": "string",
                "description": "The customer's public bank policy question, without personal data.",
            }
        },
        required=["query"],
        handler=lookup,
    )


def build_unavailable_tool() -> FunctionSchema:
    async def explain_unavailable(params: FunctionCallParams) -> None:
        await params.llm.push_frame(
            TTSSpeakFrame(
                "I can't access that information here. Please use your bank's "
                "official support channel for help."
            )
        )
        await params.result_callback(
            {"status": "unavailable"},
            properties=FunctionCallResultProperties(run_llm=False),
        )

    return FunctionSchema(
        name="explain_unavailable",
        description="Speak the fixed unavailability message for requests to access account, transaction, dispute, or identity data.",
        properties={},
        required=[],
        handler=explain_unavailable,
    )


def build_transaction_tool(
    store: DemoStore, context: VerificationContext
) -> FunctionSchema:
    async def list_transactions(params: FunctionCallParams) -> None:
        try:
            require_verified_session(
                context,
                session_id=context.session_id,
                action=TRANSACTION_READ_SCOPE,
            )
            records = TransactionReader(store.transactions(context.customer_id))
            views = records.list_customer_transactions(
                context, session_id=context.session_id
            )
            last_four = str((params.arguments or {}).get("last_four", "")).strip()
            if last_four:
                if len(last_four) != 4 or not last_four.isdigit():
                    views = ()
                else:
                    views = tuple(
                        view
                        for view in views
                        if view.masked_transaction_id.endswith(last_four)
                    )
            views = views[:5]
            if last_four and len(views) == 1:
                view = views[0]
                spoken = (
                    f"The transaction ending {last_four} is {view.merchant}, "
                    f"{view.amount} {view.currency}, {view.status}, on "
                    f"{view.occurred_at:%d %B %Y at %H:%M}. The recorded "
                    f"description is {view.bank_description}, on account "
                    f"ending {view.masked_account[-4:]}."
                )
                status = "found"
            elif views:
                details = "; ".join(
                    f"{view.merchant}, {view.amount} {view.currency}, "
                    f"{view.status}, reference ending {view.masked_transaction_id[-4:]}"
                    for view in views
                )
                spoken = f"Here is your recent activity: {details}."
                status = "found"
            else:
                spoken = "I couldn't find a matching transaction in your activity."
                status = "missing"
        except AccessDenied:
            spoken = "Please sign in again to view your activity."
            status = "verification_required"
        await params.llm.push_frame(TTSSpeakFrame(spoken))
        await params.result_callback(
            {"status": status},
            properties=FunctionCallResultProperties(run_llm=False),
        )

    return FunctionSchema(
        name="list_my_transactions",
        description="Read the signed-in customer's recent transactions, optionally matching the last four reference digits. Never ask for a full account or transaction number.",
        properties={
            "last_four": {
                "type": "string",
                "description": "Optional last four digits of a transaction reference.",
            }
        },
        required=[],
        handler=list_transactions,
    )


def build_capabilities_tool(
    has_guidance: bool, has_transactions: bool = False
) -> FunctionSchema:
    async def explain_capabilities(params: FunctionCallParams) -> None:
        if has_guidance:
            spoken = "I can answer questions from public guidance and cite the source. "
        else:
            spoken = "Public guidance is unavailable right now. "
        if has_transactions:
            spoken += "I can also review your recent activity. "
        spoken += "What would you like help with?"
        await params.llm.push_frame(TTSSpeakFrame(spoken))
        await params.result_callback(
            {"status": "capabilities_explained"},
            properties=FunctionCallResultProperties(run_llm=False),
        )

    return FunctionSchema(
        name="explain_capabilities",
        description="Explain this pilot's current capabilities when asked about its purpose or limits.",
        properties={},
        required=[],
        handler=explain_capabilities,
    )
