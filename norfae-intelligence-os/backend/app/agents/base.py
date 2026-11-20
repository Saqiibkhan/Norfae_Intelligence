import logging
import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar, cast

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentContext
from app.agents.errors import (
    AgentError,
    AgentExecutionError,
    AgentValidationError,
)
from app.agents.schemas import AgentMetadata

InputModel = TypeVar("InputModel", bound=BaseModel)
OutputModel = TypeVar("OutputModel", bound=BaseModel)
_AGENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
logger = logging.getLogger("norfae_os.agents")


class BaseAgent(ABC, Generic[InputModel, OutputModel]):
    """Common typed execution contract for LLM and deterministic agents."""

    agent_id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    input_schema: ClassVar[type[BaseModel]]
    output_schema: ClassVar[type[BaseModel]]
    required_permission: ClassVar[str | None] = None

    @classmethod
    def metadata(cls) -> AgentMetadata:
        if (
            not _AGENT_ID_PATTERN.fullmatch(cls.agent_id)
            or not cls.name.strip()
            or not cls.description.strip()
            or not issubclass(cls.input_schema, BaseModel)
            or not issubclass(cls.output_schema, BaseModel)
        ):
            raise ValueError("Agent class has incomplete or invalid metadata.")
        return AgentMetadata(
            agent_id=cls.agent_id,
            name=cls.name,
            description=cls.description,
            input_schema=cls.input_schema.__name__,
            output_schema=cls.output_schema.__name__,
            required_permission=cls.required_permission,
        )

    async def execute(
        self,
        payload: InputModel | dict[str, Any],
        *,
        context: AgentContext | None = None,
    ) -> OutputModel:
        execution_context = context or AgentContext()
        try:
            validated_input = self.input_schema.model_validate(payload)
        except ValidationError as error:
            raise AgentValidationError(
                f"Invalid input for agent '{self.agent_id}'."
            ) from error

        if self.required_permission is not None:
            execution_context.require_business_scope(self.required_permission)

        try:
            result = await self.run(validated_input, execution_context)
        except AgentError:
            raise
        except Exception as error:
            logger.error(
                "Agent execution failed",
                extra={
                    "agent_id": self.agent_id,
                    "request_id": execution_context.request_id,
                    "error_type": type(error).__name__,
                },
            )
            raise AgentExecutionError("Agent execution failed safely.") from error

        try:
            validated_output = self.output_schema.model_validate(result)
        except ValidationError as error:
            raise AgentExecutionError(
                "Agent returned output that does not match its declared schema."
            ) from error

        logger.info(
            "Agent execution completed",
            extra={
                "agent_id": self.agent_id,
                "request_id": execution_context.request_id,
            },
        )
        return cast(OutputModel, validated_output)

    @abstractmethod
    async def run(self, payload: InputModel, context: AgentContext) -> Any:
        """Implement agent-specific logic after shared validation and authorization."""
