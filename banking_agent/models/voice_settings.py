from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceSettings:
    gemini_api_key: str
    stt_model: str
    llm_model: str
    tts_model: str
    tts_voice: str
    approved_manual_index: Path | None
    demo_db_path: Path
    system_instruction: str
