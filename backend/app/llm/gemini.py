from google import genai
from google.genai import errors, types

from .base import LLMError, LLMProvider, strip_reasoning

TRANSCRIPTION_MODEL = "gemini-2.5-flash"
TRANSCRIBE_INSTRUCTION = (
    "Transcribe this audio exactly as spoken. Output only the transcription, "
    "with no commentary. If there is no intelligible speech, output nothing."
)


class GeminiProvider(LLMProvider):
    name = "gemini"
    supports_transcription = True

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

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
            raise LLMError(f"gemini request failed: {exc}") from exc
        text = strip_reasoning(response.text or "")
        if not text:
            raise LLMError("gemini returned an empty reply (possibly blocked)")
        return text

    def transcribe(self, audio, mime_type):
        # Raw bytes go straight into the Part; the SDK handles encoding.
        try:
            response = self.client.models.generate_content(
                model=TRANSCRIPTION_MODEL,
                contents=[types.Part.from_bytes(data=audio, mime_type=mime_type), TRANSCRIBE_INSTRUCTION],
            )
        except errors.APIError as exc:
            raise LLMError(f"gemini transcription failed: {exc}") from exc
        return (response.text or "").strip()
