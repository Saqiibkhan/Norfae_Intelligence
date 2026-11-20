class AgentError(Exception):
    """Base class for safe agent framework errors."""


class AgentValidationError(AgentError):
    """Agent input failed its declared Pydantic schema."""


class AgentExecutionError(AgentError):
    """Agent execution failed or returned invalid output."""


class AgentNotFoundError(AgentError):
    """No agent is registered with the requested identifier."""


class AgentAlreadyRegisteredError(AgentError):
    """An agent identifier is already registered."""


class AgentPermissionError(AgentError):
    """Required business scope or permission was not supplied."""
