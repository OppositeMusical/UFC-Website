from __future__ import annotations

import google.generativeai as genai

from app.services.ai.base import AIProvider, ProviderError


class GeminiProvider(AIProvider):
    name = "gemini"
    default_model = "gemini-1.5-flash"

    def __init__(self, api_key: str, model: str | None = None):
        genai.configure(api_key=api_key)
        self.model_name = model or self.default_model

    def generate(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str:
        generation_config = {"response_mime_type": "application/json"} if json_mode else None
        model = genai.GenerativeModel(
            self.model_name, system_instruction=system, generation_config=generation_config
        )
        # Gemini's chat history uses roles "user"/"model"; map "assistant" -> "model"
        # and send the final message as the new turn.
        history = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]}
            for m in messages[:-1]
        ]
        last_content = messages[-1]["content"] if messages else ""
        try:
            chat = model.start_chat(history=history)
            resp = chat.send_message(last_content)
        except Exception as exc:  # google-generativeai raises several distinct exception types
            raise ProviderError(f"gemini: request failed: {exc}") from exc
        return resp.text or ""

    def list_models(self) -> list[str]:
        return ["gemini-1.5-flash", "gemini-1.5-pro"]
