from __future__ import annotations

from anthropic import Anthropic, APIConnectionError, APIStatusError, AuthenticationError

from app.services.ai.base import AIProvider, ProviderError

# claude-opus-5 is Anthropic's recommended default model as of this writing.
# Users can override via Settings; list_models() offers the current lineup.
DEFAULT_MODEL = "claude-opus-5"


class AnthropicProvider(AIProvider):
    name = "claude"
    default_model = DEFAULT_MODEL

    def __init__(self, api_key: str, model: str | None = None):
        self.client = Anthropic(api_key=api_key)
        self.model = model or self.default_model

    def generate(self, messages: list[dict], system: str | None = None, json_mode: bool = False) -> str:
        anthropic_system = system
        if json_mode:
            # Anthropic's structured-output mode (output_config.format) requires a
            # JSON schema, which this generic provider interface doesn't carry -
            # so JSON mode here is a strict system-prompt instruction instead.
            json_instruction = (
                "\n\nRespond with a single valid JSON object only - no prose, "
                "no markdown code fences, no commentary before or after."
            )
            anthropic_system = (anthropic_system or "") + json_instruction
        # Omit `system` entirely when there isn't one. An explicit None is not the
        # SDK's "not given" sentinel - it serialises to `"system": null`, which the
        # API rejects with `system: Input should be a valid array`. Only Settings ->
        # Test Connection calls generate() without a system prompt, so this failed
        # exactly where a user first tries their key.
        optional: dict = {}
        if anthropic_system is not None:
            optional["system"] = anthropic_system
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=messages,
                **optional,
            )
        except AuthenticationError as exc:
            raise ProviderError("claude: API key was rejected") from exc
        except APIConnectionError as exc:
            raise ProviderError("claude: could not connect") from exc
        except APIStatusError as exc:
            raise ProviderError(f"claude: request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            raise ProviderError("claude: request was declined by safety classifiers")

        text_parts = [block.text for block in response.content if block.type == "text"]
        return "".join(text_parts)

    def list_models(self) -> list[str]:
        return ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"]
