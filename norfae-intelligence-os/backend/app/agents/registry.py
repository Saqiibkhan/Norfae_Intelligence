from app.agents.base import BaseAgent
from app.agents.errors import AgentAlreadyRegisteredError, AgentNotFoundError
from app.agents.schemas import AgentMetadata


class AgentRegistry:
    """Explicit registry for agent instances; it performs no automatic imports."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if not isinstance(agent, BaseAgent):
            raise TypeError("Only BaseAgent instances can be registered.")
        metadata = agent.metadata()
        if metadata.agent_id in self._agents:
            raise AgentAlreadyRegisteredError(
                f"Agent '{metadata.agent_id}' is already registered."
            )
        self._agents[metadata.agent_id] = agent

    def get_agent(self, agent_id: str) -> BaseAgent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise AgentNotFoundError(f"Agent '{agent_id}' is not registered.") from None

    def list_agents(self) -> list[AgentMetadata]:
        return [self._agents[key].metadata() for key in sorted(self._agents)]
