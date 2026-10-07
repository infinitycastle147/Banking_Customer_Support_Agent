from pipecat.services.google.gemini_live.stt import GeminiSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.google.tts import GeminiTTSService

from banking_agent.models.voice_settings import VoiceSettings


def build_voice_services(settings: VoiceSettings):
    stt = GeminiSTTService(
        api_key=settings.gemini_api_key,
        settings=GeminiSTTService.Settings(model=settings.stt_model),
    )
    llm = GoogleLLMService(
        api_key=settings.gemini_api_key,
        settings=GoogleLLMService.Settings(
            model=settings.llm_model,
            system_instruction=settings.system_instruction,
            max_tokens=512,
        ),
    )
    tts = GeminiTTSService(
        api_key=settings.gemini_api_key,
        use_genai=True,
        settings=GeminiTTSService.Settings(
            model=settings.tts_model,
            voice=settings.tts_voice,
            language="en-US",
        ),
    )
    return stt, llm, tts
