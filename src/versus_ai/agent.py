"""
agent.py — Agentic Debator core logic.

Two agents (Alpha=PRO, Beta=CON) debate a topic for up to MAX_TURNS rounds.
Each turn:
  1. Both agents think in parallel (asyncio.gather).
  2. Each agent may request MCP tool calls — all fired concurrently.
  3. If tools were called, agent synthesises evidence into a final argument.
  4. Agents exchange their final arguments.
  5. If either agent surrenders → verdict event emitted, loop ends.
  6. After MAX_TURNS with no surrender → caller (UI) decides winner.

All state captured in AgentTrace / Event Pydantic models from data_models.py.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import dotenv
from google import genai
from google.genai import types

# ── Path bootstrap (supports running directly or as package) ──────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from data_models import Agent, AgentTrace, Event, ToolDef  # noqa: E402

# ── Environment ───────────────────────────────────────────────────────────────
dotenv.load_dotenv(_HERE.parent.parent / ".env")

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"
MAX_TURNS = 5
PROMPTS_DIR = _HERE.parent.parent / "prompts"
MCP_SERVER_SCRIPT = _HERE / "mcp_server.py"

gemini = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════════════════
# MCP Client
# ══════════════════════════════════════════════════════════════════════════════

class MCPClient:
    """Async context manager: spawns mcp_server.py via stdio, wraps session."""

    def __init__(self) -> None:
        self._stdio_cm = None
        self._session_cm = None
        self.session = None

    async def __aenter__(self) -> "MCPClient":
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command="uv",
            args=["run", str(MCP_SERVER_SCRIPT)],
        )
        self._stdio_cm = stdio_client(params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self.session = await self._session_cm.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session_cm:
            await self._session_cm.__aexit__(*args)
        if self._stdio_cm:
            await self._stdio_cm.__aexit__(*args)

    async def list_tools(self) -> list[ToolDef]:
        result = await self.session.list_tools()
        return [
            ToolDef(
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema if isinstance(t.inputSchema, dict) else {},
            )
            for t in result.tools
        ]

    async def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self.session.call_tool(name, args)
        content = result.content
        if content:
            c = content[0]
            if hasattr(c, "text"):
                try:
                    return json.loads(c.text)
                except (json.JSONDecodeError, ValueError):
                    return {"result": c.text}
        return {"result": str(result)}


# ══════════════════════════════════════════════════════════════════════════════
# Prompt helpers
# ══════════════════════════════════════════════════════════════════════════════

def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _system_prompt(agent: Agent, tools: list[ToolDef]) -> str:
    tool_list = "\n".join(f"  - {t.name}: {t.description}" for t in tools)
    return (
        f"{agent.system_prompt}\n\n"
        f"## Available MCP Tools\n{tool_list}\n\n"
        "## Response Format\n"
        "Respond ONLY with a valid JSON object matching the Event schema:\n"
        "{\n"
        '  "kind": "llm_call",\n'
        f'  "agent_name": "{agent.name}",\n'
        '  "agent_thought": "<inner reasoning>",\n'
        '  "turn": <int>,\n'
        '  "timestamp": <float>,\n'
        '  "payload": {\n'
        '    "argument": "<your debate point>",\n'
        '    "tool_calls": [{"name": "<tool>", "args": {<args>}}],\n'
        '    "tool_results": [],\n'
        '    "surrender": false\n'
        "  },\n"
        '  "tool_name": null,\n'
        '  "tool_result": null\n'
        "}\n"
        'Set "surrender": true ONLY if opponent\'s argument is genuinely irrefutable.\n'
        'Set "tool_calls": [] if no tools needed.\n'
    )


def _to_gemini_contents(messages: list[dict[str, str]]) -> list[types.Content]:
    return [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]


# ══════════════════════════════════════════════════════════════════════════════
# LLM call helpers
# ══════════════════════════════════════════════════════════════════════════════

async def _gemini(
    system: str,
    messages: list[dict[str, str]],
) -> Event:
    """Fire one Gemini call; parse JSON response into Event manually.

    Note: response_schema=Event is NOT used because the Gemini Developer API
    rejects schemas with additionalProperties (produced by dict[str, Any]).
    We use JSON mode only and validate with Event.model_validate_json().
    """
    response = await asyncio.to_thread(
        gemini.models.generate_content,
        model=MODEL_NAME,
        contents=_to_gemini_contents(messages),
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    return Event.model_validate_json(response.text)


async def _think(
    agent: Agent,
    topic: str,
    opponent_event: Optional[Event],
    tools: list[ToolDef],
    turn: int,
) -> Event:
    """Phase 1: agent produces draft argument + optional tool_calls."""
    system = _system_prompt(agent, tools)

    messages: list[dict[str, str]] = list(agent.history)

    if opponent_event:
        opp_arg = opponent_event.payload.get("argument", "")
        user_text = (
            f"Debate topic: {topic}\n\n"
            f"Opponent's argument (Turn {turn - 1}): {opp_arg}\n\n"
            "Respond with your rebuttal. Call tools if you need evidence."
        )
    else:
        user_text = (
            f"Debate topic: {topic}\n\n"
            "Opening round — present your opening argument. "
            "Call tools if you need supporting evidence."
        )

    messages.append({"role": "user", "content": user_text})

    event = await _gemini(system, messages)
    event.agent_name = agent.name
    event.turn = turn
    event.timestamp = time.time()
    event.kind = "llm_call"
    return event


async def _synthesize(
    agent: Agent,
    topic: str,
    draft: Event,
    tool_events: list[Event],
    tools: list[ToolDef],
    turn: int,
) -> Event:
    """Phase 3: agent refines argument using tool evidence."""
    system = _system_prompt(agent, tools)
    messages: list[dict[str, str]] = list(agent.history)

    tool_summary = "\n\n".join(
        f"[{e.tool_name}] → {json.dumps(e.tool_result, indent=2)}"
        for e in tool_events
    )
    messages.append({
        "role": "user",
        "content": (
            f"Debate topic: {topic}\n\n"
            f"Your draft argument: {draft.payload.get('argument', '')}\n\n"
            f"Tool evidence gathered:\n{tool_summary}\n\n"
            "Now produce your final, evidence-backed argument. "
            'Set "tool_calls": [] in your response.'
        ),
    })

    event = await _gemini(system, messages)
    event.agent_name = agent.name
    event.turn = turn
    event.timestamp = time.time()
    event.kind = "llm_call"
    event.payload["tool_calls"] = []
    event.payload["tool_results"] = [e.tool_result for e in tool_events]
    return event


# ══════════════════════════════════════════════════════════════════════════════
# Single agent turn
# ══════════════════════════════════════════════════════════════════════════════

async def agent_turn(
    agent: Agent,
    topic: str,
    opponent_event: Optional[Event],
    tools: list[ToolDef],
    mcp: MCPClient,
    turn: int,
) -> tuple[Event, list[Event]]:
    """
    Run one full agent turn.
    Returns (final_event, all_events_this_turn).
    final_event is what the opponent will see next turn.
    """
    all_events: list[Event] = []

    # ── Phase 1: Think ────────────────────────────────────────────────────────
    draft = await _think(agent, topic, opponent_event, tools, turn)
    all_events.append(draft)

    # ── Phase 2: Concurrent tool calls ───────────────────────────────────────
    tool_calls: list[dict[str, Any]] = draft.payload.get("tool_calls", [])
    tool_events: list[Event] = []

    if tool_calls:
        async def _call_one(tc: dict[str, Any]) -> Event:
            name = tc.get("name", "")
            args = tc.get("args", {})
            result = await mcp.call_tool(name, args)
            return Event(
                kind="tool_call",
                agent_name=agent.name,
                agent_thought=f"Calling {name} with args {json.dumps(args)}",
                turn=turn,
                timestamp=time.time(),
                payload={"tool_name": name, "args": args},
                tool_name=name,
                tool_result=result,
            )

        tool_events = list(await asyncio.gather(*[_call_one(tc) for tc in tool_calls]))
        all_events.extend(tool_events)

    # ── Phase 3: Synthesise if tools were used ────────────────────────────────
    if tool_events:
        final = await _synthesize(agent, topic, draft, tool_events, tools, turn)
        all_events.append(final)
    else:
        final = draft

    # ── Update agent history ──────────────────────────────────────────────────
    opp_arg = (opponent_event.payload.get("argument", "") if opponent_event else "")
    if opp_arg:
        agent.history.append({"role": "user", "content": f"Opponent: {opp_arg}"})
    agent.history.append({"role": "model", "content": final.payload.get("argument", "")})

    return final, all_events


# ══════════════════════════════════════════════════════════════════════════════
# Debate loop — async generator
# ══════════════════════════════════════════════════════════════════════════════

async def debate_loop(topic: str) -> AsyncIterator[Event | AgentTrace]:
    """
    Async generator that yields Event objects as the debate progresses,
    then finally yields the completed AgentTrace.
    """
    started_at = time.time()
    trace = AgentTrace(goal=topic, events=[], started_at=started_at)

    # Load system prompts
    alpha_prompt = _load_prompt("sys_agent_alpha.txt")
    beta_prompt = _load_prompt("sys_agent_beta.txt")

    alpha = Agent(
        name="Agent Alpha",
        system_prompt=alpha_prompt,
        goal=f"Argue FOR: {topic}",
        history=[],
    )
    beta = Agent(
        name="Agent Beta",
        system_prompt=beta_prompt,
        goal=f"Argue AGAINST: {topic}",
        history=[],
    )

    alpha_last: Optional[Event] = None
    beta_last: Optional[Event] = None
    winner: Optional[str] = None

    async with MCPClient() as mcp:
        tools = await mcp.list_tools()

        for turn in range(1, MAX_TURNS + 1):
            # Both agents run concurrently each turn
            (alpha_final, alpha_events), (beta_final, beta_events) = await asyncio.gather(
                agent_turn(alpha, topic, beta_last, tools, mcp, turn),
                agent_turn(beta, topic, alpha_last, tools, mcp, turn),
            )

            # Yield + record all events from this turn
            for evt in alpha_events + beta_events:
                trace.events.append(evt)
                yield evt

            alpha_last = alpha_final
            beta_last = beta_final

            # ── Verdict check ─────────────────────────────────────────────────
            alpha_surrendered = alpha_final.payload.get("surrender", False)
            beta_surrendered = beta_final.payload.get("surrender", False)

            if alpha_surrendered or beta_surrendered:
                if alpha_surrendered and beta_surrendered:
                    winner = "Draw"
                elif alpha_surrendered:
                    winner = beta.name
                else:
                    winner = alpha.name

                verdict = Event(
                    kind="verdict",
                    agent_name="Moderator",
                    agent_thought=f"Debate concluded at turn {turn}.",
                    turn=turn,
                    timestamp=time.time(),
                    payload={
                        "winner": winner,
                        "reason": (
                            f"{alpha.name} surrendered." if alpha_surrendered
                            else f"{beta.name} surrendered."
                        ),
                        "alpha_argument": alpha_final.payload.get("argument", ""),
                        "beta_argument": beta_final.payload.get("argument", ""),
                    },
                    tool_name=None,
                    tool_result=None,
                )
                trace.events.append(verdict)
                yield verdict
                break

        else:
            # No surrender after MAX_TURNS — emit undecided verdict
            verdict = Event(
                kind="verdict",
                agent_name="Moderator",
                agent_thought="Max turns reached. No surrender — user must decide.",
                turn=MAX_TURNS,
                timestamp=time.time(),
                payload={
                    "winner": None,
                    "reason": "No agent surrendered after maximum turns.",
                    "alpha_argument": alpha_last.payload.get("argument", "") if alpha_last else "",
                    "beta_argument": beta_last.payload.get("argument", "") if beta_last else "",
                },
                tool_name=None,
                tool_result=None,
            )
            trace.events.append(verdict)
            yield verdict

    yield trace