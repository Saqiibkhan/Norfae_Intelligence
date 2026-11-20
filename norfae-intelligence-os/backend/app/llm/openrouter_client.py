import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from functools import lru_cache
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from app.core.config import Settings, settings
from app.llm.errors import (
    OpenRouterAuthenticationError,
    OpenRouterConfigurationError,
    OpenRouterConnectionError,
    OpenRouterProviderError,
    OpenRouterRateLimitError,
    OpenRouterTimeoutError,
)

logger = logging.getLogger("norfae_os.openrouter")

ClientFactory = Callable[..., Any]
AsyncSleeper = Callable[[float], Awaitable[None]]
_ALLOWED_ROLES = {"system", "developer", "user", "assistant", "tool"}


class OpenRouterClient:
    """Reusable async chat-completions client with bounded, safe retries."""

    def __init__(
        self,
        config: Settings | None = None,
        *,
        sdk_client: Any | None = None,
        client_factory: ClientFactory = AsyncOpenAI,
        sleeper: AsyncSleeper = asyncio.sleep,
    ) -> None:
        self._config = config or settings
        self._sdk_client = sdk_client
        self._client_factory = client_factory
        self._sleeper = sleeper

    async def chat_completion(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return the first assistant text response for the supplied messages."""
        validated_messages = self._validate_messages(messages)
        self._validate_options(temperature=temperature, max_tokens=max_tokens)

        api_key_setting = self._config.OPENROUTER_API_KEY
        api_key = api_key_setting.get_secret_value().strip() if api_key_setting else ""
        if not api_key:
            raise OpenRouterConfigurationError(
                "OpenRouter API key is not configured (OPENROUTER_API_KEY)."
            )

        client = self._get_sdk_client(api_key)
        request_options: dict[str, Any] = {
            "model": self._config.OPENROUTER_MODEL,
            "messages": validated_messages,
        }
        if temperature is not None:
            request_options["temperature"] = temperature
        if max_tokens is not None:
            request_options["max_tokens"] = max_tokens

        retries = self._config.OPENROUTER_MAX_RETRIES
        for attempt in range(retries + 1):
            try:
                response = await client.chat.completions.create(**request_options)
                return self._extract_text(response)
            except AuthenticationError:
                raise OpenRouterAuthenticationError(
                    "OpenRouter authentication failed; check OPENROUTER_API_KEY."
                ) from None
            except RateLimitError:
                if attempt < retries:
                    await self._wait_before_retry(attempt, retries)
                    continue
                raise OpenRouterRateLimitError(
                    "OpenRouter rate limit persisted after the configured retries."
                ) from None
            except APITimeoutError:
                if attempt < retries:
                    await self._wait_before_retry(attempt, retries)
                    continue
                raise OpenRouterTimeoutError(
                    "OpenRouter request timed out after the configured retries."
                ) from None
            except APIConnectionError:
                if attempt < retries:
                    await self._wait_before_retry(attempt, retries)
                    continue
                raise OpenRouterConnectionError(
                    "Could not connect to OpenRouter after the configured retries."
                ) from None
            except APIStatusError as error:
                status_code = getattr(error, "status_code", None)
                retryable_status = status_code in {408, 409} or (
                    status_code is not None and status_code >= 500
                )
                if retryable_status and attempt < retries:
                    await self._wait_before_retry(attempt, retries)
                    continue
                raise OpenRouterProviderError(
                    self._safe_status_message(status_code)
                ) from None
            except OpenAIError:
                raise OpenRouterProviderError(
                    "OpenRouter returned an error while processing the request."
                ) from None

        raise OpenRouterProviderError("OpenRouter request failed.")

    async def close(self) -> None:
        """Close the lazily-created SDK client's pooled connections, if present."""
        if self._sdk_client is not None:
            await self._sdk_client.close()
            self._sdk_client = None

    def _get_sdk_client(self, api_key: str) -> Any:
        if self._sdk_client is None:
            self._sdk_client = self._client_factory(
                api_key=api_key,
                base_url=str(self._config.OPENROUTER_BASE_URL),
                timeout=self._config.OPENROUTER_TIMEOUT,
                # The service owns retry policy; disable the SDK's implicit retries.
                max_retries=0,
            )
        return self._sdk_client

    async def _wait_before_retry(self, attempt: int, retries: int) -> None:
        delay = min(0.25 * (2**attempt), 2.0)
        logger.warning(
            "OpenRouter request failed with a transient error; retry %d of %d.",
            attempt + 1,
            retries,
        )
        await self._sleeper(delay)

    @staticmethod
    def _safe_status_message(status_code: int | None) -> str:
        if status_code is None:
            return "OpenRouter returned an unsuccessful response."
        return f"OpenRouter returned an unsuccessful response (HTTP {status_code})."

    @staticmethod
    def _validate_messages(
        messages: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        if isinstance(messages, (str, bytes)) or not isinstance(messages, Sequence) or not messages:
            raise ValueError("messages must be a non-empty sequence of chat messages.")

        validated: list[dict[str, Any]] = []
        for index, message in enumerate(messages):
            if not isinstance(message, Mapping):
                raise ValueError(f"messages[{index}] must be a mapping.")
            role = message.get("role")
            if not isinstance(role, str) or role not in _ALLOWED_ROLES:
                raise ValueError(f"messages[{index}].role is not a supported chat role.")
            content = message.get("content")
            if not isinstance(content, (str, list)) or not content:
                raise ValueError(
                    f"messages[{index}].content must contain text or content parts."
                )
            validated.append(dict(message))
        return validated

    @staticmethod
    def _validate_options(
        *, temperature: float | None, max_tokens: int | None
    ) -> None:
        if temperature is not None and (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not 0 <= temperature <= 2
        ):
            raise ValueError("temperature must be a number between 0 and 2.")
        if max_tokens is not None and (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or max_tokens < 1
        ):
            raise ValueError("max_tokens must be a positive integer.")

    @staticmethod
    def _extract_text(response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError):
            raise OpenRouterProviderError(
                "OpenRouter returned an invalid chat completion response."
            ) from None
        if not isinstance(content, str):
            raise OpenRouterProviderError(
                "OpenRouter response did not contain assistant text."
            )
        return content


@lru_cache(maxsize=1)
def get_openrouter_client() -> OpenRouterClient:
    """Return the process-wide reusable OpenRouter client instance."""
    return OpenRouterClient()
