import io

import openai

from .base import LLMError, LLMProvider, strip_reasoning


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI itself, or any server speaking its API (Ollama, vLLM, LM Studio, DashScope for Qwen...)."""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str | None = None,
        transcription_model: str | None = None,
        send_temperature: bool = True,
    ):
        self.name = name
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=90, max_retries=2)
        self.transcription_model = transcription_model
        self.supports_transcription = transcription_model is not None
        # OpenAI reasoning models reject non-default temperatures, so it is only sent to self-hosted models.
        self.send_temperature = send_temperature

    def complete(self, model, system, messages, *, json_mode=False, temperature=0.7):
        payload = [{"role": "system", "content": system}]
        payload += [{"role": m.role, "content": m.content} for m in messages]
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self.send_temperature:
            kwargs["temperature"] = temperature
        try:
            response = self.client.chat.completions.create(model=model, messages=payload, **kwargs)
        except openai.OpenAIError as exc:
            raise LLMError(f"{self.name} request failed: {exc}") from exc
        text = strip_reasoning(response.choices[0].message.content or "") if response.choices else ""
        if not text:
            raise LLMError(f"{self.name} returned an empty reply")
        return text

    def transcribe(self, audio, mime_type):
        if not self.transcription_model:
            return super().transcribe(audio, mime_type)
        extension = mime_type.split("/")[-1].split(";")[0] or "wav"
        file = io.BytesIO(audio)
        file.name = f"recording.{extension}"
        try:
            result = self.client.audio.transcriptions.create(model=self.transcription_model, file=file)
        except openai.OpenAIError as exc:
            raise LLMError(f"{self.name} transcription failed: {exc}") from exc
        return result.text.strip()
