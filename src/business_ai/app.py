from business_ai.agents import build_agents
from business_ai.core.orchestrator import Orchestrator
from business_ai.memory.store import InMemoryContextStore


def build_orchestrator() -> Orchestrator:
    return Orchestrator(agents=build_agents(), memory=InMemoryContextStore())
