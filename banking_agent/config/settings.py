import os
from datetime import timedelta
from pathlib import Path

from banking_agent.models.voice_settings import VoiceSettings

PUBLIC_GUIDANCE_INSTRUCTION = (
    "You route requests in a local banking support prototype. Produce no prose. "
    "For every public guidance question call search_approved_manual with a short "
    "query that contains no personal data. For account, transaction, dispute, "
    "identity, or other unsupported requests call explain_unavailable. "
    "Never ask for names, account numbers, passwords, card details, or one-time codes."
)

VERIFICATION_MAX_AGE = timedelta(minutes=5)
TRANSACTION_READ_SCOPE = "transactions:read"
DISPUTE_READ_SCOPE = "disputes:read"
DISPUTE_WRITE_SCOPE = "disputes:write"
MAX_TRANSACTION_RESULTS = 20
CONSENT_MAX_AGE = timedelta(minutes=2)
PILOT_CUSTOMER_REQUEST_LIMIT_PER_HOUR = 5
PILOT_SESSION_REQUEST_LIMIT_PER_HOUR = 3
PILOT_TARGET_REQUEST_LIMIT_PER_HOUR = 2
PILOT_MUTABLE_DISPUTE_STATES = frozenset({"pending_review"})
PILOT_OUTBOX_MAX_ATTEMPTS = 3
OUTBOX_POLL_INTERVAL_SECONDS = 1


def load_voice_settings() -> VoiceSettings:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is required to start the voice pilot")

    index_path = os.getenv("APPROVED_MANUAL_INDEX", "").strip()
    return VoiceSettings(
        gemini_api_key=api_key,
        stt_model=os.getenv("GEMINI_STT_MODEL", "gemini-3.5-transcribe-live"),
        llm_model=os.getenv("GEMINI_LLM_MODEL", "gemini-3.1-flash-lite"),
        tts_model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview"),
        tts_voice=os.getenv("GEMINI_TTS_VOICE", "Kore"),
        approved_manual_index=Path(index_path) if index_path else None,
        system_instruction=PUBLIC_GUIDANCE_INSTRUCTION,
    )
