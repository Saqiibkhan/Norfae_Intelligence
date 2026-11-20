from pydantic import BaseModel, ConfigDict


class AgentMetadata(BaseModel):
    """Public, non-sensitive description of a registered agent."""

    agent_id: str
    name: str
    description: str
    input_schema: str
    output_schema: str
    required_permission: str | None = None

    model_config = ConfigDict(frozen=True)
