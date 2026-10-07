from dataclasses import dataclass


@dataclass(frozen=True)
class CommandOutcome:
    code: str
    message: str
    correlation_id: str
    request_id: str | None = None
    request_state: str | None = None
    retryable: bool = False
