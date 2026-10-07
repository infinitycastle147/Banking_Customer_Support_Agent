import logging

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
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

from banking_agent.config.settings import load_voice_settings
from banking_agent.knowledge.retrieval import load_approved_passages
from banking_agent.voice.services import build_voice_services
from banking_agent.voice.tools import build_public_guidance_tool

logger = logging.getLogger(__name__)


async def bot(runner_args: RunnerArguments) -> None:
    settings = load_voice_settings()
    passages = load_approved_passages(settings.approved_manual_index)
    transport = await create_transport(
        runner_args,
        {
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True, audio_out_enabled=True
            )
        },
    )
    stt, llm, tts = build_voice_services(settings)
    context = LLMContext(tools=[build_public_guidance_tool(passages)])
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
        context.add_message(
            {
                "role": "developer",
                "content": "Give the opening notice, then ask for a public guidance question.",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

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
