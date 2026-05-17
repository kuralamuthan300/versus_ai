from pydantic import BaseModel, Field
from typing import Any, Literal

class Agent(BaseModel):
    name: str = Field(description="Name of the Agent")
    system_prompt: str = Field(description="System Prompt of the Agent")
    goal: str = Field(description="Goal of the Agent")
    history: list[dict] = Field(description="History of the Agent")

class ToolDef(BaseModel):
    name: str = Field(description="Name of the Tool")
    description: str = Field(description="Description of the Tool")
    input_schema: dict[str, Any] = Field(description="Input Schema of the Tool")

class Event(BaseModel):
    kind: Literal["llm_call", "tool_call", "verdict"]= Field(description="Type of the Event")
    agent_name: str= Field(description="Name of the Agent")
    agent_thought: str= Field(description="Agent's Thought")
    turn: int= Field(description="Turn number")
    timestamp: float= Field(description="Timestamp of the event")
    payload: dict[str, Any]= Field(description="Payload of the event")
    tool_name: str | None = Field(default=None, description="Name of the Tool")
    tool_result: dict | None = Field(default=None, description="Result of the Tool")

class AgentTrace(BaseModel):
    goal: str= Field(description="Goal of the System")
    events: list[Event]= Field(description="List of Events")
    started_at: float= Field(description="Timestamp of the start of the System")
