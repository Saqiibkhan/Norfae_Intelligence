import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx2
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)
from pydantic import SecretStr

from app.core.config import Settings
from app.llm.errors import (
    OpenRouterAuthenticationError,
    OpenRouterConfigurationError,
    OpenRouterConnectionError,
    OpenRouterProviderError,
    OpenRouterRateLimitError,
    OpenRouterTimeoutError,
)
from app.llm.openrouter_client import OpenRouterClient

TEST_API_KEY = "sk-or-unit-test-secret"
TEST_DB_URL = "postgresql+psycopg2://test:test@127.0.0.1:1/norfae_test"


def run(coroutine):
    return asyncio.run(coroutine)


def make_settings(*, api_key=TEST_API_KEY, retries=2, **overrides):
    values = {
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "OPENROUTER_MODEL": "test/provider-model",
        "OPENROUTER_TIMEOUT": 7.5,
        "OPENROUTER_MAX_RETRIES": retries,
    }
    values.update(overrides)
    return Settings(
        DATABASE_URL=TEST_DB_URL,
        OPENROUTER_API_KEY=(SecretStr(api_key) if api_key is not None else None),
        _env_file=None,
        **values,
    )


def make_response(content="Test answer"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def make_error_response(status_code):
    request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return request, httpx2.Response(status_code, request=request)


class FakeSDKClient:
    def __init__(self, *, result=None, side_effect=None):
        create = AsyncMock(return_value=result, side_effect=side_effect)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=create),
        )
        self.close = AsyncMock()


async def no_sleep(_delay):
    return None


def test_settings_load_and_secret_is_masked():
    config = make_settings()

    assert config.OPENROUTER_API_KEY.get_secret_value() == TEST_API_KEY
    assert str(config.OPENROUTER_BASE_URL) == "https://openrouter.ai/api/v1"
    assert config.OPENROUTER_MODEL == "test/provider-model"
    assert config.OPENROUTER_TIMEOUT == 7.5
    assert config.OPENROUTER_MAX_RETRIES == 2
    assert TEST_API_KEY not in repr(config)


def test_openrouter_settings_have_safe_defaults_without_a_key():
    config = Settings(
        DATABASE_URL=TEST_DB_URL,
        OPENROUTER_API_KEY=None,
        _env_file=None,
    )

    assert str(config.OPENROUTER_BASE_URL) == "https://openrouter.ai/api/v1"
    assert config.OPENROUTER_MODEL
    assert config.OPENROUTER_TIMEOUT > 0
    assert config.OPENROUTER_MAX_RETRIES == 2


def test_missing_api_key_raises_safe_configuration_error():
    factory = Mock()
    client = OpenRouterClient(
        make_settings(api_key=None),
        client_factory=factory,
        sleeper=no_sleep,
    )

    with pytest.raises(OpenRouterConfigurationError, match="OPENROUTER_API_KEY"):
        run(client.chat_completion([{"role": "user", "content": "Hello"}]))

    factory.assert_not_called()


def test_client_uses_configured_model_base_url_timeout_and_single_retry_owner():
    sdk_client = FakeSDKClient(result=make_response())
    factory = Mock(return_value=sdk_client)
    client = OpenRouterClient(
        make_settings(), client_factory=factory, sleeper=no_sleep
    )

    answer = run(
        client.chat_completion(
            [{"role": "user", "content": "Hello"}],
            temperature=0.3,
            max_tokens=40,
        )
    )

    assert answer == "Test answer"
    factory.assert_called_once_with(
        api_key=TEST_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=7.5,
        max_retries=0,
    )
    sdk_client.chat.completions.create.assert_awaited_once_with(
        model="test/provider-model",
        messages=[{"role": "user", "content": "Hello"}],
        temperature=0.3,
        max_tokens=40,
    )


def test_authentication_error_is_not_retried_or_exposed(caplog):
    request, response = make_error_response(401)
    auth_error = AuthenticationError(
        f"Rejected key {TEST_API_KEY}",
        response=response,
        body={"error": {"message": TEST_API_KEY}},
    )
    sdk_client = FakeSDKClient(side_effect=auth_error)
    client = OpenRouterClient(
        make_settings(retries=3), sdk_client=sdk_client, sleeper=no_sleep
    )

    with caplog.at_level("WARNING"):
        with pytest.raises(OpenRouterAuthenticationError) as caught:
            run(client.chat_completion([{"role": "user", "content": "Hello"}]))

    assert sdk_client.chat.completions.create.await_count == 1
    assert TEST_API_KEY not in str(caught.value)
    assert TEST_API_KEY not in caplog.text


def test_rate_limit_retries_stop_at_configured_limit():
    _, response = make_error_response(429)
    sdk_client = FakeSDKClient(
        side_effect=RateLimitError("Try later", response=response, body={})
    )
    client = OpenRouterClient(
        make_settings(retries=2), sdk_client=sdk_client, sleeper=no_sleep
    )

    with pytest.raises(OpenRouterRateLimitError, match="configured retries"):
        run(client.chat_completion([{"role": "user", "content": "Hello"}]))

    assert sdk_client.chat.completions.create.await_count == 3


def test_server_errors_stop_after_configured_retry_limit():
    request, response = make_error_response(503)
    sdk_client = FakeSDKClient(
        side_effect=[
            InternalServerError("provider detail", response=response, body={}),
        ] * 3
    )
    client = OpenRouterClient(
        make_settings(retries=2), sdk_client=sdk_client, sleeper=no_sleep
    )

    with pytest.raises(OpenRouterProviderError, match="HTTP 503"):
        run(client.chat_completion([{"role": "user", "content": "Hello"}]))

    assert sdk_client.chat.completions.create.await_count == 3


@pytest.mark.parametrize(
    ("sdk_error", "application_error"),
    [
        ("timeout", OpenRouterTimeoutError),
        ("connection", OpenRouterConnectionError),
    ],
)
def test_timeout_and_network_errors_are_bounded_and_sanitized(
    sdk_error, application_error, caplog
):
    request, _ = make_error_response(500)
    if sdk_error == "timeout":
        error = APITimeoutError(request=request)
    else:
        error = APIConnectionError(
            message=f"Network details containing {TEST_API_KEY}", request=request
        )
    sdk_client = FakeSDKClient(side_effect=error)
    client = OpenRouterClient(
        make_settings(retries=1), sdk_client=sdk_client, sleeper=no_sleep
    )

    with caplog.at_level("WARNING"):
        with pytest.raises(application_error) as caught:
            run(client.chat_completion([{"role": "user", "content": "Hello"}]))

    assert sdk_client.chat.completions.create.await_count == 2
    assert TEST_API_KEY not in str(caught.value)
    assert TEST_API_KEY not in caplog.text


def test_invalid_provider_response_becomes_safe_application_error():
    sdk_client = FakeSDKClient(result=SimpleNamespace(choices=[]))
    client = OpenRouterClient(
        make_settings(), sdk_client=sdk_client, sleeper=no_sleep
    )

    with pytest.raises(OpenRouterProviderError, match="invalid chat completion"):
        run(client.chat_completion([{"role": "user", "content": "Hello"}]))


def test_invalid_chat_inputs_are_rejected_before_provider_call():
    sdk_client = FakeSDKClient(result=make_response())
    client = OpenRouterClient(
        make_settings(), sdk_client=sdk_client, sleeper=no_sleep
    )

    with pytest.raises(ValueError, match="non-empty sequence"):
        run(client.chat_completion([]))
    with pytest.raises(ValueError, match="supported chat role"):
        run(client.chat_completion([{"role": "system-admin", "content": "Hello"}]))

    sdk_client.chat.completions.create.assert_not_awaited()


def test_retry_and_timeout_settings_enforce_safe_bounds():
    with pytest.raises(ValueError):
        make_settings(OPENROUTER_TIMEOUT=0)
    with pytest.raises(ValueError):
        make_settings(OPENROUTER_MAX_RETRIES=6)
    with pytest.raises(ValueError):
        make_settings(OPENROUTER_BASE_URL="http://openrouter.example/api/v1")
