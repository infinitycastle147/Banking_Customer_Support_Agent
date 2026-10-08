from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import FunctionCallResultProperties, TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams

from banking_agent.knowledge.retrieval import search_approved_manual
from banking_agent.models.manual_passage import ManualPassage


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
                "This prototype cannot access accounts, transactions, or disputes. "
                "Please use your bank's official support channel for help."
            )
        )
        await params.result_callback(
            {"status": "unavailable"},
            properties=FunctionCallResultProperties(run_llm=False),
        )

    return FunctionSchema(
        name="explain_unavailable",
        description="Speak the fixed unavailability message for account, transaction, dispute, identity, or other unsupported requests.",
        properties={},
        required=[],
        handler=explain_unavailable,
    )
