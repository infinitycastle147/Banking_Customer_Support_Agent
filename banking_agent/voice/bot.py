import logging

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import TransportParams
from pipecat.workers.runner import WorkerRunner

from banking_agent.banking.demo_store import DemoStore
from banking_agent.config.settings import load_voice_settings
from banking_agent.knowledge.retrieval import load_approved_passages
from banking_agent.voice.services import build_voice_services
from banking_agent.voice.speech_gate import PublicSpeechGate
from banking_agent.voice.tools import (
    build_capabilities_tool,
    build_greeting_tool,
    build_public_guidance_tool,
    build_transaction_tool,
    build_unavailable_tool,
)

logger = logging.getLogger(__name__)


async def bot(runner_args: RunnerArguments) -> None:
    settings = load_voice_settings()
    passages = load_approved_passages(settings.approved_manual_index)
    body = runner_args.body if isinstance(runner_args.body, dict) else {}
    ticket = body.get("voice_ticket", "")
    store = DemoStore(settings.demo_db_path)
    verified_context = store.redeem_voice_ticket(ticket)
    transport = await create_transport(
        runner_args,
        {
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True, audio_out_enabled=True
            )
        },
    )
    stt, llm, tts = build_voice_services(settings)
    tools = [
        build_greeting_tool(),
        build_capabilities_tool(bool(passages), verified_context is not None),
        build_public_guidance_tool(passages),
        build_unavailable_tool(),
    ]
    if verified_context:
        tools.append(build_transaction_tool(store, verified_context))
    context = LLMContext(tools=tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            PublicSpeechGate(),
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    latency_observer = UserBotLatencyObserver()

    @latency_observer.event_handler("on_latency_measured")
    async def on_latency_measured(_observer, latency_seconds: float) -> None:
        logger.info("voice.latency_measured seconds=%.3f", latency_seconds)

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True),
        observers=[latency_observer],
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(_rtvi) -> None:
        await tts.queue_frame(
            TTSSpeakFrame("Welcome to Harbor Support. How can I help?")
        )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client) -> None:
        logger.info("voice.session_started")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client) -> None:
        logger.info("voice.session_ended")
        await runner.cancel()

    await runner.add_workers(worker)
    await runner.run()


def main() -> None:
    from pipecat.runner.run import main as run_pipecat

    run_pipecat()


if __name__ == "__main__":
    main()
