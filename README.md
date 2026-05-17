# Versus AI — Agentic Debater

Two AI agents debate any topic head-to-head. **Agent Alpha** argues in favour (PRO), and **Agent Beta** argues against (CON). Each turn, both agents think independently, call MCP tools (web search, URL fetch) to gather real evidence, and then deliver a concise, three-sentence rebuttal. The debate runs for up to 5 turns; whichever agent surrenders first loses. If neither surrenders, the human audience casts the deciding vote.

## Features

- **Gemini‑2.5‑Flash** powers both agents (Google Gemini API).
- **MCP tools** (`web_search`, `fetch_url`) give agents live internet access for evidence.
- **Gradio UI** for a polished, real‑time streaming experience.
- **CLI mode** for headless debugging or automation.
- **Structured JSON output** — every thought, tool call, and argument is captured as typed `Event` objects.
- **Prompt Evaluation** — every system prompt is benchmarked against a formal rubric (see below).

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Set your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 3. Launch the Gradio UI
uv run main.py

# 4. Or run headless on the CLI
uv run main.py --cli "AI will replace all software engineers by 2030"
```

Open `http://localhost:7860` in your browser, enter a topic, and click **Start Debate**.

## Project Structure

```
versus_ai/
├── main.py                    # Entry point (UI or CLI)
├── sys_prompt_evaluation.md   # Rubric for evaluating system prompts
├── prompts/
│   ├── sys_agent_alpha.txt    # System prompt for Agent Alpha (PRO side)
│   └── sys_agent_beta.txt     # System prompt for Agent Beta (CON side)
├── src/versus_ai/
│   ├── agent.py               # Core debate loop, MCP client, LLM calls
│   ├── app.py                 # Gradio UI
│   ├── data_models.py         # Pydantic models (Agent, Event, AgentTrace, ToolDef)
│   └── mcp_server.py          # MCP server exposing web_search & fetch_url tools
├── pyproject.toml
└── README.md
```

## How the Debate Works

```
┌─────────────────────────────────────────────────────────────┐
│                    DEBATE LOOP (up to 5 turns)              │
│                                                             │
│  Turn N                                                     │
│  ┌─────────────────┐         ┌─────────────────┐           │
│  │   Agent Alpha   │         │   Agent Beta    │           │
│  │   (PRO side)    │         │   (CON side)    │           │
│  │                 │         │                 │           │
│  │  1. Think ──────┼─────────┼──► 1. Think     │           │
│  │  2. Tool calls  │         │  2. Tool calls  │           │
│  │  3. Synthesise  │         │  3. Synthesise  │           │
│  └────────┬────────┘         └────────┬────────┘           │
│           │                           │                    │
│           └──────────┬────────────────┘                    │
│                      │                                     │
│               Exchange arguments                            │
│                      │                                     │
│            Check surrender conditions                       │
│                      │                                     │
│         ┌────────────┴────────────┐                        │
│         │ Any surrendered?       │                         │
│         │   YES → emit verdict   │                         │
│         │   NO  → next turn      │                         │
│         └────────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### Agent Turn — Three Phases

1. **Think** — The agent receives the opponent's last argument and produces a draft rebuttal with optional tool requests.
2. **Tool Calls** — All requested MCP tools (`web_search`, `fetch_url`) are fired concurrently. Results are collected.
3. **Synthesise** — The agent refines its draft into a final, evidence-backed argument (max 3 sentences). The opponent sees only this final argument.

### Surrender & Verdict

- Each agent carries a `surrender` flag in its payload.
- An agent surrenders **only** when the opponent presents multiple pieces of irrefutable, source-backed evidence that completely dismantles its position.
- If **Alpha surrenders** → Beta wins.
- If **Beta surrenders** → Alpha wins.
- If **both surrender** → Draw.
- If **neither surrenders after 5 turns** → the human audience votes.

---

## Prompt Evaluation

Every system prompt in this project is evaluated against a formal rubric defined in [`sys_prompt_evaluation.md`](./sys_prompt_evaluation.md). This section explains the evaluation criteria, how each prompt is scored, and the results.

### Evaluation Rubric

The rubric defines **9 criteria** used to assess how well a prompt supports structured, step-by-step reasoning in an LLM:

| # | Criterion | Description |
|---|-----------|-------------|
| 1 | **Explicit Reasoning Instructions** | Does the prompt tell the model to reason step-by-step ("explain your thinking", "think before you answer")? |
| 2 | **Structured Output Format** | Does the prompt enforce a predictable output format (JSON, numbered steps, etc.) that is easy to parse? |
| 3 | **Separation of Reasoning & Tools** | Are reasoning steps clearly separated from computation/tool-use steps? |
| 4 | **Conversation Loop Support** | Can the prompt work in a multi-turn setting with context from previous steps? |
| 5 | **Instructional Framing** | Are there examples or format definitions showing exactly how responses should look? |
| 6 | **Internal Self-Checks** | Does the prompt instruct the model to self-verify or sanity-check intermediate steps? |
| 7 | **Reasoning Type Awareness** | Does the prompt encourage tagging or identifying the type of reasoning used (logic, calculation, lookup, assumption)? |
| 8 | **Error Handling / Fallbacks** | Does the prompt specify what to do if uncertain, a tool fails, or the model is unsure? |
| 9 | **Overall Clarity & Robustness** | Is the prompt easy to follow? Is it likely to reduce hallucination and drift? |

Each criterion is scored `true`/`false` (or a qualitative assessment for clarity) and compiled into a structured JSON review.

### How Evaluation Is Performed

1. A **Prompt Evaluation Assistant** (a separate LLM agent or script) reads the system prompt file (`sys_agent_alpha.txt`, `sys_agent_beta.txt`, etc.).
2. The assistant scores the prompt against each of the 9 criteria, producing a JSON response like:
   ```json
   {
     "explicit_reasoning": true,
     "structured_output": true,
     "tool_separation": true,
     "conversation_loop": true,
     "instructional_framing": true,
     "internal_self_checks": true,
     "reasoning_type_awareness": true,
     "fallbacks": false,
     "overall_clarity": "Excellent structure with clear tool separation. Consider adding error fallbacks."
   }
   ```
3. The evaluation results are used to iteratively improve prompts — weak criteria (e.g., missing fallbacks) become targets for the next revision.

### Evaluation of Current Prompts

#### Agent Alpha (`sys_agent_alpha.txt`)

| Criterion | Score | Justification |
|-----------|-------|---------------|
| Explicit Reasoning | ✅ | "Reason step by step and think before you answer" — explicitly instructed. |
| Structured Output | ✅ | The agent responds in a strict JSON Event schema enforced by `_system_prompt()` in `agent.py`. |
| Tool Separation | ✅ | Reasoning (Phase 1) is fully separated from tool calls (Phase 2) and synthesis (Phase 3). |
| Conversation Loop | ✅ | Each turn passes opponent's argument and maintains agent history across turns. |
| Instructional Framing | ✅ | The prompt defines a clear debate strategy (opening, evidence, rebuttal, escalation). |
| Internal Self-Checks | ✅ | "Always self-verify the answers before responding" and "Make sure there is no contradiction." |
| Reasoning Type Awareness | ✅ | Explicitly requires tagging each step with `Reasoning Type: [Logic \| Calculation \| Lookup \| Assumption]` plus Explanation and Confidence Score. |
| Error Handling / Fallbacks | ⚠️ Partial | "If you don't have enough evidence from the tool then use your reasoning skills" is a partial fallback, but there's no handling for tool failures or API errors. |
| Overall Clarity | Strong | Well-structured with clear role, strategy, tool usage rules, surrender conditions, and tone. Concise at 38 lines. |

#### Agent Beta (`sys_agent_beta.txt`)

| Criterion | Score | Justification |
|-----------|-------|---------------|
| Explicit Reasoning | ✅ | "Reason step by step and think before you answer" — identical instruction. |
| Structured Output | ✅ | Same JSON Event schema enforced. |
| Tool Separation | ✅ | Same three-phase architecture (think → tools → synthesise). |
| Conversation Loop | ✅ | Same history mechanism across turns. |
| Instructional Framing | ✅ | Clear CON-side strategy: challenge assumptions, expose fallacies, highlight risks. |
| Internal Self-Checks | ✅ | "Always self-verify" and "Make sure there is no contradiction." |
| Reasoning Type Awareness | ✅ | Tagging with Reasoning Type, Explanation, and Confidence Score. |
| Error Handling / Fallbacks | ⚠️ Partial | Same partial fallback as Alpha ("If you don't have enough evidence… use reasoning skills"). |
| Overall Clarity | Strong | Mirror structure to Alpha but tuned for CON-side argumentation. Slightly longer at 39 lines but equally clear. |

### Key Strengths

- **Reasoning type tagging** forces agents to explicitly identify *how* they arrived at each conclusion, making the thought process transparent.
- **Confidence scoring** adds a self-aware dimension — the model must assess its own certainty at each step.
- **Three-phase architecture** cleanly separates thinking from tool use from synthesis, preventing tool calls from polluting reasoning.
- **Surrender conditions** are formalised with high bars ("irrefutable, source-backed evidence") to avoid premature surrender.

### Areas for Improvement

1. **Tool failure fallbacks** — Neither prompt specifies what to do if `web_search` or `fetch_url` returns an error, times out, or returns empty results. Adding a fallback such as *"If a tool call fails or returns no results, note the failure and proceed with logical reasoning alone"* would improve robustness.
2. **Uncertainty handling** — The prompts could benefit from an explicit instruction for low-confidence scenarios, e.g., *"If your Confidence Score is below 0.5, present the argument as a hypothesis rather than a fact."*
3. **Contradiction resolution** — While the prompts say "no contradiction," they don't specify how to resolve contradictions between tool evidence and prior reasoning. A resolution strategy (e.g., *"If tool evidence contradicts your earlier reasoning, acknowledge the contradiction and revise your argument"*) would help.

### How to Run an Evaluation

```bash
# Example: have an LLM evaluate one of the prompts against the rubric
# (pseudo-code — integrate with your LLM of choice)
cat prompts/sys_agent_alpha.txt | your-llm --system "$(cat sys_prompt_evaluation.md)" \
  --prompt "Evaluate this prompt using the rubric above. Return JSON."
```

See [`sys_prompt_evaluation.md`](./sys_prompt_evaluation.md) for the full rubric specification.

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Google Gemini API key. |
| `MODEL_NAME` | `gemini-2.5-flash` | Gemini model for both agents. |
| `MAX_TURNS` | `5` | Maximum debate rounds before user vote. |

## Requirements

- Python ≥ 3.11
- `uv` package manager
- Google Gemini API key

## License

MIT

---

*README.md written by Cline bot.*