"""
app.py — Gradio UI for the Versus AI Agentic Debater.

Layout:
  • Topic input + Start Debate button
  • Live-streaming debate transcript (Alpha left, Beta right)
  • Tool-call expandable sections
  • Verdict banner or User-Vote panel when agents can't decide
"""

from __future__ import annotations

import asyncio
import html
import sys
import time
from pathlib import Path
from typing import Any

import gradio as gr

# ── Path bootstrap ────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from agent import debate_loop, MAX_TURNS  # noqa: E402
from data_models import AgentTrace, Event  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# HTML / CSS helpers
# ══════════════════════════════════════════════════════════════════════════════

ALPHA_COLOR = "#6366f1"   # indigo
BETA_COLOR  = "#f43f5e"   # rose
TOOL_COLOR  = "#0ea5e9"   # sky

CSS = """
/* ── Global ────────────────────────────────────────────────────────────── */
body, .gradio-container {
    background: #f8fafc !important;
    font-family: 'Inter', sans-serif;
    color: #0f172a;
}
h1.title {
    text-align: center;
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4f46e5 0%, #e11d48 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
p.subtitle {
    text-align: center;
    color: #475569;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

/* ── Transcript card ────────────────────────────────────────────────────── */
.transcript-wrap {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1.5rem;
    min-height: 400px;
    max-height: 620px;
    overflow-y: auto;
    scroll-behavior: smooth;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
.turn-header {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #94a3b8;
    margin: 1.4rem 0 0.5rem;
}
.bubble {
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    line-height: 1.6;
    font-size: 0.95rem;
    max-width: 88%;
}
.bubble-alpha {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    color: #1e293b;
}
.bubble-beta {
    background: #fff1f2;
    border-left: 4px solid #f43f5e;
    color: #1e293b;
    margin-left: auto;
}
.agent-label {
    font-size: 0.78rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
}
.label-alpha { color: #2563eb; }
.label-beta  { color: #e11d48; }
.thought-block {
    font-size: 0.8rem;
    color: #64748b;
    font-style: italic;
    margin-bottom: 0.5rem;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 0.4rem;
}
.tool-chip {
    display: inline-block;
    background: #f0f9ff;
    border: 1px solid #7dd3fc;
    color: #0369a1;
    border-radius: 8px;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 10px;
    margin: 2px 4px 2px 0;
}
.tool-result-block {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
    font-size: 0.75rem;
    color: #334155;
    font-family: monospace;
    margin-top: 0.4rem;
    max-height: 120px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

/* ── Status bar ─────────────────────────────────────────────────────────── */
.status-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.6rem 1rem;
    font-size: 0.85rem;
    color: #475569;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
}
.status-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #4f46e5;
    animation: pulse 1.4s infinite;
}
.status-dot.idle   { background: #cbd5e1; animation: none; }
.status-dot.done   { background: #22c55e; animation: none; }
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
}

/* ── Verdict banner ─────────────────────────────────────────────────────── */
.verdict-banner {
    background: #ffffff;
    border: 2px solid #4f46e5;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    margin-top: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
.verdict-banner.alpha-wins { border-color: #3b82f6; background: #eff6ff; }
.verdict-banner.beta-wins  { border-color: #f43f5e; background: #fff1f2; }
.verdict-banner.draw       { border-color: #f59e0b; background: #fffbeb; }
.verdict-title {
    font-size: 1.8rem;
    font-weight: 900;
    margin-bottom: 0.4rem;
    color: #0f172a;
}
.verdict-reason {
    color: #475569;
    font-size: 0.9rem;
}

/* ── Vote panel ─────────────────────────────────────────────────────────── */
.vote-panel {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1.5rem;
    text-align: center;
    margin-top: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
.vote-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 1rem;
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# Transcript renderer
# ══════════════════════════════════════════════════════════════════════════════

def _esc(s: str) -> str:
    return html.escape(str(s))


def _tool_chip(name: str) -> str:
    return f'<span class="tool-chip">⚙ {_esc(name)}</span>'


def _tool_result_block(result: dict[str, Any] | None) -> str:
    if not result:
        return ""
    import json
    text = json.dumps(result, indent=2)[:600]
    return f'<div class="tool-result-block">{_esc(text)}</div>'


def render_event(evt: Event, show_tools: bool = True) -> str:
    """Convert an Event to an HTML snippet for the transcript."""
    if evt.kind == "tool_call":
        if not show_tools:
            return ""
        return (
            f'<div style="margin: 4px 0 4px 12px;">'
            f'{_tool_chip(evt.tool_name or "tool")}'
            f'{_tool_result_block(evt.tool_result)}'
            f'</div>'
        )

    is_alpha = "alpha" in evt.agent_name.lower()
    side_cls = "bubble-alpha" if is_alpha else "bubble-beta"
    label_cls = "label-alpha" if is_alpha else "label-beta"
    icon = "🔵" if is_alpha else "🔴"

    tool_calls: list[dict] = evt.payload.get("tool_calls", [])
    tool_chips_html = "".join(_tool_chip(tc.get("name", "")) for tc in tool_calls)

    argument = _esc(evt.payload.get("argument", ""))
    thought = _esc(evt.agent_thought or "")

    surrender_badge = (
        '<span style="background:#fbbf24;color:#000;border-radius:6px;'
        'padding:1px 8px;font-size:0.7rem;font-weight:700;margin-left:8px;">'
        '⚑ SURRENDERED</span>'
        if evt.payload.get("surrender") else ""
    )

    return (
        f'<div class="bubble {side_cls}">'
        f'  <div class="agent-label {label_cls}">{icon} {_esc(evt.agent_name)}{surrender_badge}</div>'
        f'  <div class="thought-block">💭 {thought}</div>'
        f'  <div>{argument}</div>'
        f'  {"<div style=margin-top:6px>" + tool_chips_html + "</div>" if tool_chips_html else ""}'
        f'</div>'
    )


def render_verdict(payload: dict[str, Any]) -> str:
    winner = payload.get("winner")
    reason = _esc(payload.get("reason", ""))

    if winner == "Agent Alpha":
        css_class, icon, title = "alpha-wins", "🏆", "Agent Alpha Wins!"
    elif winner == "Agent Beta":
        css_class, icon, title = "beta-wins", "🏆", "Agent Beta Wins!"
    elif winner == "Draw":
        css_class, icon, title = "draw", "🤝", "It's a Draw!"
    else:
        return ""  # undecided — handled by vote panel

    return (
        f'<div class="verdict-banner {css_class}">'
        f'  <div class="verdict-title">{icon} {_esc(title)}</div>'
        f'  <div class="verdict-reason">{reason}</div>'
        f'</div>'
    )


def status_bar(state: str, text: str) -> str:
    return (
        f'<div class="status-bar">'
        f'  <div class="status-dot {state}"></div>'
        f'  <span>{_esc(text)}</span>'
        f'</div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# Gradio app
# ══════════════════════════════════════════════════════════════════════════════

def build_app() -> gr.Blocks:
    with gr.Blocks(title="Versus AI — Agentic Debater") as demo:

        # ── Header ────────────────────────────────────────────────────────────
        gr.HTML(
            '<h1 class="title">⚔️ Versus AI</h1>'
            '<p class="subtitle">Two AI agents debate any topic — watch them think, research, and argue.</p>'
        )

        # ── Topic input row ───────────────────────────────────────────────────
        with gr.Row():
            topic_box = gr.Textbox(
                label="Debate Topic",
                placeholder="e.g. AI will replace all software engineers by 2030",
                scale=5,
                container=True,
            )
            start_btn = gr.Button("⚔️ Start Debate", variant="primary", scale=1, min_width=160)

        # ── Status bar ────────────────────────────────────────────────────────
        status_html = gr.HTML(status_bar("idle", "Ready — enter a topic and click Start Debate."))

        # ── Transcript ────────────────────────────────────────────────────────
        transcript_html = gr.HTML(
            '<div class="transcript-wrap" id="transcript"></div>'
        )

        # ── Verdict banner ────────────────────────────────────────────────────
        verdict_html = gr.HTML(visible=False)

        # ── User vote panel ───────────────────────────────────────────────────
        with gr.Column(visible=False) as vote_col:
            gr.HTML(
                '<div class="vote-panel">'
                '<div class="vote-title">🗳️ The agents couldn\'t decide — cast your vote!</div>'
                '</div>'
            )
            with gr.Row():
                vote_alpha = gr.Button("🔵 Agent Alpha Won", variant="primary")
                vote_draw  = gr.Button("🤝 Draw")
                vote_beta  = gr.Button("🔴 Agent Beta Won", variant="secondary")

        user_verdict_html = gr.HTML(visible=False)

        # ── State holders ─────────────────────────────────────────────────────
        trace_state: gr.State = gr.State(None)

        # ══════════════════════════════════════════════════════════════════════
        # Debate runner (async generator → Gradio streaming)
        # ══════════════════════════════════════════════════════════════════════

        async def run_debate(topic: str):
            if not topic.strip():
                yield (
                    status_bar("idle", "⚠ Please enter a debate topic."),
                    '<div class="transcript-wrap"></div>',
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    None,
                )
                return

            # Reset UI
            transcript_blocks: list[str] = []
            current_turn = 0

            yield (
                status_bar("active", "🔄 Connecting to MCP server and initialising agents…"),
                '<div class="transcript-wrap" id="transcript"></div>',
                gr.update(value="", visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                None,
            )

            collected_trace = None

            async for item in debate_loop(topic):
                if isinstance(item, AgentTrace):
                    collected_trace = item
                    continue

                evt: Event = item

                # Turn header
                if evt.kind == "llm_call" and evt.turn != current_turn:
                    current_turn = evt.turn
                    transcript_blocks.append(
                        f'<div class="turn-header">── Turn {current_turn} of {MAX_TURNS} ──</div>'
                    )

                if evt.kind == "verdict":
                    winner = evt.payload.get("winner")
                    if winner:
                        # Agents decided
                        verdict_block = render_verdict(evt.payload)
                        transcript_inner = "\n".join(transcript_blocks)
                        yield (
                            status_bar("done", f"✅ Debate concluded — {winner} wins!"),
                            f'<div class="transcript-wrap" id="transcript">{transcript_inner}</div>',
                            gr.update(value=verdict_block, visible=True),
                            gr.update(visible=False),
                            gr.update(visible=False),
                            collected_trace,
                        )
                    else:
                        # No winner — show vote panel
                        transcript_inner = "\n".join(transcript_blocks)
                        yield (
                            status_bar("done", "🤔 No verdict reached — you decide!"),
                            f'<div class="transcript-wrap" id="transcript">{transcript_inner}</div>',
                            gr.update(value="", visible=False),
                            gr.update(visible=True),
                            gr.update(visible=False),
                            collected_trace,
                        )
                    return

                # Normal event → render and stream
                block = render_event(evt)
                if block:
                    transcript_blocks.append(block)

                transcript_inner = "\n".join(transcript_blocks)
                turn_label = f"Turn {current_turn}/{MAX_TURNS}"
                agent_label = evt.agent_name if evt.kind == "llm_call" else f"{evt.agent_name} → {evt.tool_name}"
                yield (
                    status_bar("active", f"🧠 {turn_label} · {agent_label}…"),
                    f'<div class="transcript-wrap" id="transcript">{transcript_inner}</div>',
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    None,
                )

        start_btn.click(
            fn=run_debate,
            inputs=[topic_box],
            outputs=[status_html, transcript_html, verdict_html, vote_col, user_verdict_html, trace_state],
        )
        topic_box.submit(
            fn=run_debate,
            inputs=[topic_box],
            outputs=[status_html, transcript_html, verdict_html, vote_col, user_verdict_html, trace_state],
        )

        # ══════════════════════════════════════════════════════════════════════
        # User vote handlers
        # ══════════════════════════════════════════════════════════════════════

        def _make_vote_handler(choice: str):
            def handler():
                if choice == "Alpha":
                    banner = (
                        '<div class="verdict-banner alpha-wins">'
                        '<div class="verdict-title">🏆 You voted: Agent Alpha Wins!</div>'
                        '<div class="verdict-reason">Decided by the audience.</div></div>'
                    )
                elif choice == "Beta":
                    banner = (
                        '<div class="verdict-banner beta-wins">'
                        '<div class="verdict-title">🏆 You voted: Agent Beta Wins!</div>'
                        '<div class="verdict-reason">Decided by the audience.</div></div>'
                    )
                else:
                    banner = (
                        '<div class="verdict-banner draw">'
                        '<div class="verdict-title">🤝 You declared it a Draw!</div>'
                        '<div class="verdict-reason">Both sides made compelling points.</div></div>'
                    )
                return gr.update(value=banner, visible=True), gr.update(visible=False)

            return handler

        vote_alpha.click(
            fn=_make_vote_handler("Alpha"),
            outputs=[user_verdict_html, vote_col],
        )
        vote_draw.click(
            fn=_make_vote_handler("Draw"),
            outputs=[user_verdict_html, vote_col],
        )
        vote_beta.click(
            fn=_make_vote_handler("Beta"),
            outputs=[user_verdict_html, vote_col],
        )

    return demo


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = build_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        css=CSS,
        theme=gr.themes.Base(
            primary_hue="indigo",
            neutral_hue="slate",
            font=gr.themes.GoogleFont("Inter"),
        ),
    )
