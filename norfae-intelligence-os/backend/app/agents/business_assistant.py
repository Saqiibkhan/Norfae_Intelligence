from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agents.base import BaseAgent
from app.agents.context import AgentContext
from app.schemas.assistant_schema import AssistantChatRequest, AssistantChatResponse


class BusinessAssistantAgent(BaseAgent[AssistantChatRequest, AssistantChatResponse]):
    agent_id = "business_assistant"
    name = "AI Business Assistant"
    description = "Grounded natural-language answers over approved tenant intelligence tools."
    input_schema = AssistantChatRequest
    output_schema = AssistantChatResponse
    required_permission = "analytics:read"

    async def run(self, payload: AssistantChatRequest, context: AgentContext) -> Any:
        db = context.get_business_dependency("db", self.required_permission)
        service = context.get_dependency("business_assistant_service")
        return await service.chat(db, context, payload)
