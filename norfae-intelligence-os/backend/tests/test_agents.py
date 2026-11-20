import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from app.agents import AgentContext, AgentRegistry, BaseAgent
from app.agents.errors import (
    AgentAlreadyRegisteredError,
    AgentExecutionError,
    AgentNotFoundError,
    AgentPermissionError,
    AgentValidationError,
)
from app.agents.examples import TextStatsAgent, TextStatsInput, TextStatsOutput
from app.llm.openrouter_client import OpenRouterClient


def run(coroutine):
    return asyncio.run(coroutine)


class NumberInput(BaseModel):
    value: int


class NumberOutput(BaseModel):
    doubled: int


class ScopedOutput(BaseModel):
    business_id: str
    service_name: str


class ScopedAgent(BaseAgent[NumberInput, ScopedOutput]):
    agent_id = "test.scoped"
    name = "Scoped Test Agent"
    description = "Checks that explicit business authorization is required."
    input_schema = NumberInput
    output_schema = ScopedOutput
    required_permission = "orders:read"

    async def run(self, payload: NumberInput, context: AgentContext) -> dict[str, str]:
        del payload
        business_id = context.require_business_scope(self.required_permission)
        service = context.get_business_dependency(
            "approved_service", self.required_permission
        )
        return {"business_id": business_id, "service_name": service}


class BrokenAgent(BaseAgent[NumberInput, NumberOutput]):
    agent_id = "test.broken"
    name = "Broken Test Agent"
    description = "Raises an implementation error for error handling tests."
    input_schema = NumberInput
    output_schema = NumberOutput

    async def run(self, payload: NumberInput, context: AgentContext) -> Any:
        del payload, context
        raise RuntimeError("internal detail must remain out of the safe message")


class InvalidOutputAgent(BaseAgent[NumberInput, NumberOutput]):
    agent_id = "test.invalid_output"
    name = "Invalid Output Test Agent"
    description = "Returns a value that does not match its output schema."
    input_schema = NumberInput
    output_schema = NumberOutput

    async def run(self, payload: NumberInput, context: AgentContext) -> Any:
        del payload, context
        return {"doubled": "not-an-integer"}


class OpenRouterAdapterAgent(BaseAgent[TextStatsInput, TextStatsOutput]):
    agent_id = "test.openrouter_adapter"
    name = "OpenRouter Adapter Test Agent"
    description = "Verifies injection of the existing centralized LLM client."
    input_schema = TextStatsInput
    output_schema = TextStatsOutput

    async def run(
        self, payload: TextStatsInput, context: AgentContext
    ) -> dict[str, int]:
        client = context.get_dependency("openrouter")
        reply = await client.chat_completion(
            [{"role": "user", "content": payload.text}], max_tokens=16
        )
        return {"word_count": len(reply.split()), "character_count": len(reply)}


def test_base_agent_is_abstract():
    with pytest.raises(TypeError):
        BaseAgent()


def test_sample_agent_executes_asynchronously_and_returns_typed_output():
    result = run(TextStatsAgent().execute({"text": "Norfae intelligence platform"}))

    assert isinstance(result, TextStatsOutput)
    assert result.model_dump() == {"word_count": 3, "character_count": 28}


def test_agent_input_validation_is_controlled_and_does_not_echo_input():
    sensitive_input = "private-customer-data"
    with pytest.raises(AgentValidationError) as caught:
        run(TextStatsAgent().execute({"text": [sensitive_input]}))

    assert "Invalid input" in str(caught.value)
    assert sensitive_input not in str(caught.value)


def test_agent_output_validation_is_controlled():
    with pytest.raises(AgentExecutionError, match="does not match"):
        run(InvalidOutputAgent().execute({"value": 2}))


def test_agent_execution_error_is_safe_and_preserves_original_exception():
    with pytest.raises(AgentExecutionError) as caught:
        run(BrokenAgent().execute({"value": 2}))

    assert str(caught.value) == "Agent execution failed safely."
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert "internal detail" in str(caught.value.__cause__)


def test_business_agent_fails_closed_without_business_scope():
    with pytest.raises(AgentPermissionError, match="business scope"):
        run(ScopedAgent().execute({"value": 1}, context=AgentContext()))


def test_business_agent_fails_closed_without_required_permission():
    context = AgentContext(
        business_id="business-123",
        permissions=frozenset({"products:read"}),
    )

    with pytest.raises(AgentPermissionError, match="business scope"):
        run(ScopedAgent().execute({"value": 1}, context=context))


def test_authorized_context_supplies_only_explicit_scope_and_dependencies():
    context = AgentContext(
        user_id="user-123",
        business_id="business-123",
        permissions=frozenset({"orders:read"}),
        request_id="request-123",
        dependencies={"approved_service": "read-only-orders"},
    )

    result = run(ScopedAgent().execute({"value": 1}, context=context))

    assert result.model_dump() == {
        "business_id": "business-123",
        "service_name": "read-only-orders",
    }
    assert "read-only-orders" not in repr(context)
    assert "dependencies" not in context.model_dump()


def test_agent_registry_registers_retrieves_and_lists_metadata():
    registry = AgentRegistry()
    text_agent = TextStatsAgent()
    scoped_agent = ScopedAgent()

    registry.register(scoped_agent)
    registry.register(text_agent)

    assert registry.get_agent(text_agent.agent_id) is text_agent
    metadata = registry.list_agents()
    assert [item.agent_id for item in metadata] == [
        "example.text_stats",
        "test.scoped",
    ]
    assert metadata[0].input_schema == "TextStatsInput"
    assert metadata[1].required_permission == "orders:read"


def test_agent_registry_rejects_duplicate_registration():
    registry = AgentRegistry()
    registry.register(TextStatsAgent())

    with pytest.raises(AgentAlreadyRegisteredError, match="already registered"):
        registry.register(TextStatsAgent())


def test_agent_registry_reports_unknown_identifiers():
    with pytest.raises(AgentNotFoundError, match="not registered"):
        AgentRegistry().get_agent("not.here")


def test_context_reports_missing_injected_dependency_safely():
    with pytest.raises(AgentExecutionError, match="not available"):
        AgentContext().get_dependency("missing")


def test_business_dependency_access_requires_scope_and_permission():
    context = AgentContext(dependencies={"orders": "scoped read service"})

    with pytest.raises(AgentPermissionError):
        context.get_business_dependency("orders", "orders:read")


def test_openrouter_client_can_be_injected_without_creating_a_second_client():
    existing_client = Mock(spec=OpenRouterClient)
    existing_client.chat_completion = AsyncMock(return_value="A concise answer")
    context = AgentContext(dependencies={"openrouter": existing_client})

    result = run(
        OpenRouterAdapterAgent().execute(
            {"text": "Explain the revenue trend."}, context=context
        )
    )

    assert result.model_dump() == {"word_count": 3, "character_count": 16}
    existing_client.chat_completion.assert_awaited_once_with(
        [{"role": "user", "content": "Explain the revenue trend."}],
        max_tokens=16,
    )
