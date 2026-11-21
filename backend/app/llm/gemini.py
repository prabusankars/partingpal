import httpx
from google import genai
from google.genai import errors, types

from .base import LLMError, LLMProvider, strip_reasoning

TRANSCRIBE_INSTRUCTION = (
    "Transcribe this audio exactly as spoken. Output only the transcription, "
    "with no commentary. If there is no intelligible speech, output nothing."
)


class GeminiProvider(LLMProvider):
    name = "gemini"
    supports_transcription = True

    def __init__(self, api_key: str, *, transcription_model: str, timeout_seconds: int):
        # Without a timeout a busy model leaves the employee's message spinning indefinitely.
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000))
        self.transcription_model = transcription_model

    def complete(self, model, system, messages, *, json_mode=False, temperature=0.7):
        contents = [
            types.Content(role="user" if m.role == "user" else "model", parts=[types.Part.from_text(text=m.content)])
            for m in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_mode else None,
        )
        try:
            response = self.client.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as exc:
            raise LLMError(f"gemini request failed ({model}): {exc}") from exc
        except httpx.HTTPError as exc:  # timeouts and connection failures are not APIErrors
            raise LLMError(f"gemini request failed ({model}): {type(exc).__name__}: {exc}") from exc
        text = strip_reasoning(response.text or "")
        if not text:
            raise LLMError("gemini returned an empty reply (possibly blocked)")
        return text

    def transcribe(self, audio, mime_type):
        # Raw bytes go straight into the Part; the SDK handles encoding.
        try:
            response = self.client.models.generate_content(
                model=self.transcription_model,
                contents=[types.Part.from_bytes(data=audio, mime_type=mime_type), TRANSCRIBE_INSTRUCTION],
            )
        except (errors.APIError, httpx.HTTPError) as exc:
            raise LLMError(f"gemini transcription failed ({self.transcription_model}): {exc}") from exc
        return (response.text or "").strip()
