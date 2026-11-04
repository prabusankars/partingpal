from dataclasses import dataclass
from functools import lru_cache

from ..config import get_settings
from .base import LLMError, LLMProvider

LABELS = {
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "oss": "Open source (Qwen, Llama… via Ollama / vLLM)",
}


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    label: str
    models: list[str]
    available: bool


def is_configured(provider: str) -> bool:
    s = get_settings()
    return {
        "openai": bool(s.openai_api_key),
        "gemini": bool(s.gemini_api_key),
        "oss": bool(s.oss_base_url),
    }.get(provider, False)


def list_providers() -> list[ProviderInfo]:
    s = get_settings()
    return [ProviderInfo(pid, label, s.models_for(pid), is_configured(pid)) for pid, label in LABELS.items()]


@lru_cache
def get_provider(provider: str) -> LLMProvider:
    s = get_settings()
    if not is_configured(provider):
        raise LLMError(f"Provider '{provider}' is not configured")
    if provider == "openai":
        from .openai_compat import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            "openai", s.openai_api_key, transcription_model=s.openai_transcription_model, send_temperature=False
        )
    if provider == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(s.gemini_api_key)
    if provider == "oss":
        from .openai_compat import OpenAICompatibleProvider

        return OpenAICompatibleProvider("oss", s.oss_api_key, base_url=s.oss_base_url)
    raise LLMError(f"Unknown provider '{provider}'")


def resolve_model(provider: str | None, model: str | None) -> tuple[str, str]:
    """Validate an HR-selected provider/model pair, falling back to defaults."""
    s = get_settings()
    provider = provider or s.default_provider
    if provider not in LABELS:
        raise LLMError(f"Unknown provider '{provider}'")
    if not is_configured(provider):
        raise LLMError(f"Provider '{provider}' is not configured on the server")
    models = s.models_for(provider)
    if not models:
        raise LLMError(f"No models configured for '{provider}'")
    model = model or models[0]
    if model not in models:
        raise LLMError(f"Model '{model}' is not enabled for '{provider}'")
    return provider, model


def get_transcriber() -> LLMProvider | None:
    s = get_settings()
    candidates = [s.transcription_provider] if s.transcription_provider else ["openai", "gemini"]
    for candidate in candidates:
        if candidate and is_configured(candidate):
            provider = get_provider(candidate)
            if provider.supports_transcription:
                return provider
    return None
