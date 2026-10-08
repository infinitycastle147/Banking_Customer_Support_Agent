from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import FunctionCallResultProperties, TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams

from banking_agent.knowledge.retrieval import search_approved_manual
from banking_agent.models.manual_passage import ManualPassage


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
        description="Speak the fixed unavailability message for requests to access account, transaction, dispute, or identity data.",
        properties={},
        required=[],
        handler=explain_unavailable,
    )


def build_capabilities_tool(has_guidance: bool) -> FunctionSchema:
    async def explain_capabilities(params: FunctionCallParams) -> None:
        if has_guidance:
            spoken = (
                "I can answer questions from approved public guidance and cite the source. "
                "I cannot access your account or process disputes in this pilot. "
                "What public guidance would you like to ask about?"
            )
        else:
            spoken = (
                "This is a test of the voice interface. No approved bank guidance is "
                "loaded yet, so I cannot answer bank policy questions in this session. "
                "I also cannot access accounts or process disputes. For banking help, "
                "please use your bank's official support channel."
            )
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
