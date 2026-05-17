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

### Evaluation of Current Prompts (Prompt Content Only)

The following evaluations consider **only the text within the prompt files themselves** — no assumptions are made about how the surrounding code (`agent.py`) enforces additional structure.

The prompts were recently updated to satisfy **all 9 criteria** in the rubric. Below is the evaluation against the current versions.

#### Agent Alpha (`sys_agent_alpha.txt`)

| # | Criterion | Score | Justification |
|---|-----------|-------|---------------|
| 1 | Explicit Reasoning | ✅ | "Reason step by step and think before you answer" — explicitly instructed. |
| 2 | Structured Output | ✅ | "## Response Format" section defines the Event JSON schema fields (`argument`, `tool_calls`, `tool_results`, `surrender`) and tells the model the exact JSON schema will follow. |
| 3 | Tool Separation | ✅ | "## Three-Phase Workflow" cleanly separates into Phase 1 (Think), Phase 2 (Call Tools), Phase 3 (Synthesise) with distinct instructions for each. |
| 4 | Conversation Loop | ✅ | "You are in a multi-turn debate. Each turn you will receive the opponent's last argument. Respond accordingly with your rebuttal." — explicitly stated in ## Your Role. |
| 5 | Instructional Framing | ✅ | "## Response Format" provides example structure for `agent_thought` ("Reasoning Type: Logic\nExplanation: ...\nConfidence Score: 0.85") and defines payload field descriptions. |
| 6 | Internal Self-Checks | ✅ | "Always self verify the answers before responding" and "Make sure there is no contradiction in your answer" plus Phase 3: "Ensure no contradictions between your reasoning and tool results." |
| 7 | Reasoning Type Awareness | ✅ | Requires tagging each step with `Reasoning Type: [Logic \| Calculation \| Lookup \| Assumption]`, Explanation, and Confidence Score (0.0 to 1.0). |
| 8 | Error Handling / Fallbacks | ✅ | Covers: tool failure ("If a tool call fails, returns an error, times out, or returns empty results, note the failure... proceed using logical reasoning alone"), low confidence ("If your Confidence Score is below 0.5, flag it as uncertain reasoning"), and insufficient evidence ("If you dont have enough evidence from the tool then use your reasoning skills"). |
| 9 | Overall Clarity | Strong | Well-organised with Role, Three-Phase Workflow, Debate Strategy, Tool Usage, Response Format, Surrender Condition, and Tone sections. 78 lines, comprehensive but scannable. |

#### Agent Beta (`sys_agent_beta.txt`)

| # | Criterion | Score | Justification |
|---|-----------|-------|---------------|
| 1 | Explicit Reasoning | ✅ | "Reason step by step and think before you answer" — identical instruction. |
| 2 | Structured Output | ✅ | Same "## Response Format" section with JSON schema fields and example thought structure. |
| 3 | Tool Separation | ✅ | Same "## Three-Phase Workflow" (Think → Call Tools → Synthesise). |
| 4 | Conversation Loop | ✅ | Same multi-turn debate instruction in ## Your Role. |
| 5 | Instructional Framing | ✅ | Provides example thought structure and explains payload field requirements. |
| 6 | Internal Self-Checks | ✅ | "Always self verify" and contradiction check in Phase 3. |
| 7 | Reasoning Type Awareness | ✅ | Same reasoning type tagging with Confidence Score (0.0 to 1.0). |
| 8 | Error Handling / Fallbacks | ✅ | Same coverage: tool failure fallback, low-confidence flagging (below 0.5), insufficient evidence fallback. |
| 9 | Overall Clarity | Strong | Mirror structure to Alpha, tuned for CON-side argumentation. 80 lines, equally clear. |

### Key Strengths (After Update)

- **All 9 rubric criteria satisfied** — Both prompts now pass every evaluation criterion from `sys_prompt_evaluation.md`.
- **Three-Phase Workflow** cleanly separates thinking (Phase 1), tool use (Phase 2), and synthesis (Phase 3) into explicit, ordered steps.
- **Comprehensive error handling** — Tool failures, timeouts, empty results, low-confidence scenarios, and insufficient evidence are all covered with specific fallback instructions.
- **Conversation loop awareness** — Both prompts explicitly inform the agent it is in a multi-turn debate and will receive the opponent's argument each turn.
- **Instructional framing with examples** — The `agent_thought` example shows exactly how reasoning tags should be formatted.
- **Contradiction resolution** — Phase 3 instructs agents to acknowledge and resolve contradictions between tool evidence and prior reasoning.

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