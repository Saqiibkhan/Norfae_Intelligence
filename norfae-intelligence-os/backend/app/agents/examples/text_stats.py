from pydantic import BaseModel, ConfigDict, Field

from app.agents.base import BaseAgent
from app.agents.context import AgentContext


class TextStatsInput(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)

    model_config = ConfigDict(str_strip_whitespace=True)


class TextStatsOutput(BaseModel):
    word_count: int = Field(ge=0)
    character_count: int = Field(ge=0)


class TextStatsAgent(BaseAgent[TextStatsInput, TextStatsOutput]):
    agent_id = "example.text_stats"
    name = "Text Statistics Example"
    description = "Counts words and characters without calling an LLM."
    input_schema = TextStatsInput
    output_schema = TextStatsOutput

    async def run(
        self, payload: TextStatsInput, context: AgentContext
    ) -> dict[str, int]:
        del context  # This deterministic example does not need caller services.
        return {
            "word_count": len(payload.text.split()),
            "character_count": len(payload.text),
        }
