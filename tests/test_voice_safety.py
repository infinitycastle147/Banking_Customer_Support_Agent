import asyncio
from datetime import date

from pipecat.frames.frames import LLMTextFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection

from banking_agent.models.manual_passage import ManualPassage
from banking_agent.models.source_reference import SourceReference
from banking_agent.voice.speech_gate import PublicSpeechGate
from banking_agent.voice.tools import (
    build_capabilities_tool,
    build_greeting_tool,
    build_public_guidance_tool,
    build_unavailable_tool,
)


class FakeLLM:
    def __init__(self):
        self.frames = []

    async def push_frame(self, frame):
        self.frames.append(frame)


class FakeCall:
    def __init__(self, arguments):
        self.arguments = arguments
        self.llm = FakeLLM()
        self.result = None
        self.properties = None

    async def result_callback(self, result, *, properties):
        self.result = result
        self.properties = properties


def test_model_text_is_silenced_but_scripted_speech_passes():
    gate = PublicSpeechGate()
    frames = []

    async def capture(frame, direction):
        frames.append((frame, direction))

    gate.push_frame = capture
    generated = LLMTextFrame("An unsupported bank policy claim")
    scripted = TTSSpeakFrame("Approved guidance is unavailable.")

    async def exercise():
        await gate.process_frame(generated, FrameDirection.DOWNSTREAM)
        await gate.process_frame(scripted, FrameDirection.DOWNSTREAM)

    asyncio.run(exercise())

    assert generated.skip_tts
    assert frames[0][0] is generated
    assert frames[1][0] is scripted
    assert not hasattr(scripted, "skip_tts")


def test_approved_lookup_speaks_exact_passage_and_source():
    passage = ManualPassage(
        reference=SourceReference(
            document_id="synthetic-demo-handbook",
            version="1.0",
            section="Demo help hours",
            effective_date=date(2026, 1, 1),
            owner="Demo documentation owner",
            source_hash="a" * 64,
        ),
        text="Fictional support hours are 09:00 to 17:00.",
        keywords=("support hours",),
        expires_on=date(2027, 1, 1),
        classification="public",
    )
    call = FakeCall({"query": "support hours"})

    asyncio.run(build_public_guidance_tool((passage,)).handler(call))

    assert call.result == {"status": "found"}
    assert call.properties.run_llm is False
    assert len(call.llm.frames) == 1
    assert isinstance(call.llm.frames[0], TTSSpeakFrame)
    assert call.llm.frames[0].text == (
        "Fictional support hours are 09:00 to 17:00. "
        "Source: synthetic-demo-handbook, version 1.0, section Demo help hours."
    )


def test_missing_guidance_and_unsupported_request_use_fixed_messages():
    lookup_call = FakeCall({"query": "unknown policy"})
    unsupported_call = FakeCall({})

    asyncio.run(build_public_guidance_tool(()).handler(lookup_call))
    asyncio.run(build_unavailable_tool().handler(unsupported_call))

    assert lookup_call.result == {"status": "missing"}
    assert "Approved guidance is unavailable" in lookup_call.llm.frames[0].text
    assert unsupported_call.result == {"status": "unavailable"}
    assert "can't access that information" in unsupported_call.llm.frames[0].text
    assert unsupported_call.properties.run_llm is False


def test_capabilities_response_reflects_loaded_guidance():
    empty_call = FakeCall({})
    loaded_call = FakeCall({})

    asyncio.run(build_capabilities_tool(False).handler(empty_call))
    asyncio.run(build_capabilities_tool(True).handler(loaded_call))

    assert "Public guidance is unavailable" in empty_call.llm.frames[0].text
    assert "public guidance" in loaded_call.llm.frames[0].text
    assert empty_call.result == {"status": "capabilities_explained"}
    assert loaded_call.properties.run_llm is False


def test_simple_greeting_does_not_recite_capabilities():
    call = FakeCall({})

    asyncio.run(build_greeting_tool().handler(call))

    assert call.llm.frames[0].text == "Hello. How can I help?"
    assert call.result == {"status": "greeted"}
    assert call.properties.run_llm is False
