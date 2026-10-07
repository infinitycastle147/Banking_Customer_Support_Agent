from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.services.llm_service import FunctionCallParams

from banking_agent.knowledge.retrieval import search_approved_manual
from banking_agent.models.manual_passage import ManualPassage


def build_public_guidance_tool(passages: tuple[ManualPassage, ...]) -> FunctionSchema:
    async def lookup(params: FunctionCallParams) -> None:
        query = (params.arguments or {}).get("query", "")
        result = search_approved_manual(query, passages)
        await params.result_callback(
            {
                "status": result.status,
                "passages": [
                    {
                        "text": passage.text,
                        "document_id": passage.reference.document_id,
                        "version": passage.reference.version,
                        "section": passage.reference.section,
                        "effective_date": passage.reference.effective_date.isoformat(),
                        "classification": passage.classification,
                    }
                    for passage in result.passages
                ],
            }
        )

    return FunctionSchema(
        name="search_approved_manual",
        description="Search approved public bank guidance. Missing or conflicting means do not answer from memory.",
        properties={
            "query": {
                "type": "string",
                "description": "The customer's public bank policy question, without personal data.",
            }
        },
        required=["query"],
        handler=lookup,
    )
