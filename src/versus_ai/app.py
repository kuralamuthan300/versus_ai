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
/* ── Global Theme Overrides to FORCE Light Mode ────────────────────────── */
:root, .dark, body, gradio-app, .gradio-container {
    --body-background-fill: #ffffff !important;
    --background-fill-primary: #ffffff !important;
    --background-fill-secondary: #f8fafc !important;
    --border-color-primary: #e2e8f0 !important;
    --border-color-accent: #3b82f6 !important;
    --body-text-color: #0f172a !important;
    --body-text-color-subdued: #475569 !important;
    --block-background-fill: #ffffff !important;
    --block-label-text-color: #334155 !important;
    --input-background-fill: #ffffff !important;
    --input-border-color: #cbd5e1 !important;
    --button-primary-background-fill: #3b82f6 !important;
    --button-primary-text-color: #ffffff !important;
    --button-secondary-background-fill: #f1f5f9 !important;
    --button-secondary-text-color: #0f172a !important;
    --color-accent: #3b82f6 !important;
    --panel-background-fill: #ffffff !important;
}

/* ── Global ────────────────────────────────────────────────────────────── */
body, .gradio-container, .dark {
    background: var(--body-background-fill) !important;
    color: var(--body-text-color) !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
h1.title {
    text-align: center;
    font-size: 2rem;
    font-weight: 600;
    color: #0f172a !important;
    margin-bottom: 0.5rem;
    letter-spacing: -0.02em;
}
p.subtitle {
    text-align: center;
    color: #475569 !important;
    font-size: 1rem;
    margin-bottom: 2rem;
}

/* ── Transcript card ────────────────────────────────────────────────────── */
.transcript-wrap {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px;
    padding: 1.5rem;
    min-height: 400px;
    max-height: 650px;
    overflow-y: auto;
    scroll-behavior: smooth;
}
.turn-header {
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #64748b !important;
    margin: 2rem 0 1rem;
    text-align: center;
}
.bubble {
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    line-height: 1.6;
    font-size: 0.95rem;
    max-width: 85%;
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    color: #0f172a !important;
}
.bubble-alpha {
    border-left: 3px solid #3b82f6 !important;
}
.bubble-beta {
    border-left: 3px solid #ef4444 !important;
    margin-left: auto;
}
.agent-label {
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    color: #0f172a !important;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.thought-block {
    font-size: 0.875rem;
    color: #475569 !important;
    margin-bottom: 1rem;
    padding-left: 1rem;
    border-left: 2px solid #cbd5e1 !important;
}
.tool-chip {
    display: inline-block;
    background: #f1f5f9 !important;
    border: 1px solid #cbd5e1 !important;
    color: #334155 !important;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 2px 8px;
    margin: 4px 4px 0 0;
}
.tool-result-block {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-size: 0.8rem;
    color: #1e293b !important;
    font-family: 'ui-monospace', 'SFMono-Regular', monospace;
    margin-top: 0.5rem;
    max-height: 150px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

/* ── Status bar ─────────────────────────────────────────────────────────── */
.status-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: #334155 !important;
    margin-bottom: 1rem;
}
.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #3b82f6 !important;
    animation: pulse 1.5s infinite;
}
.status-dot.idle   { background: #cbd5e1 !important; animation: none; }
.status-dot.done   { background: #10b981 !important; animation: none; }
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
}

/* ── Verdict banner ─────────────────────────────────────────────────────── */
.verdict-banner {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    margin-top: 1.5rem;
}
.verdict-banner.alpha-wins { border-top: 4px solid #3b82f6 !important; }
.verdict-banner.beta-wins  { border-top: 4px solid #ef4444 !important; }
.verdict-banner.draw       { border-top: 4px solid #10b981 !important; }
.verdict-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
    color: #0f172a !important;
}
.verdict-reason {
    color: #475569 !important;
    font-size: 0.95rem;
}

/* ── Vote panel ─────────────────────────────────────────────────────────── */
.vote-panel {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    margin-top: 1.5rem;
}
.vote-title {
    font-size: 1.1rem;
    font-weight: 500;
    color: #0f172a !important;
    margin-bottom: 1.5rem;
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# Transcript renderer
# ══════════════════════════════════════════════════════════════════════════════

def _esc(s: str) -> str:
    return html.escape(str(s))


def _tool_chip(name: str) -> str:
    return f'<span class="tool-chip">{_esc(name)}</span>'


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

    tool_calls: list[dict] = evt.payload.get("tool_calls", [])
    tool_chips_html = "".join(_tool_chip(tc.get("name", "")) for tc in tool_calls)

    argument = _esc(evt.payload.get("argument", ""))
    thought = _esc(evt.agent_thought or "")

    surrender_badge = (
        '<span style="background:#fef3c7;color:#92400e;border-radius:4px;'
        'padding:2px 6px;font-size:0.7rem;font-weight:600;margin-left:8px;">'
        'SURRENDERED</span>'
        if evt.payload.get("surrender") else ""
    )

    return (
        f'<div class="bubble {side_cls}">'
        f'  <div class="agent-label {label_cls}">{_esc(evt.agent_name)}{surrender_badge}</div>'
        f'  <div class="thought-block">{thought}</div>'
        f'  <div>{argument}</div>'
        f'  {"<div style=margin-top:8px>" + tool_chips_html + "</div>" if tool_chips_html else ""}'
        f'</div>'
    )


def render_verdict(payload: dict[str, Any]) -> str:
    winner = payload.get("winner")
    reason = _esc(payload.get("reason", ""))

    if winner == "Agent Alpha":
        css_class, title = "alpha-wins", "Agent Alpha Wins"
    elif winner == "Agent Beta":
        css_class, title = "beta-wins", "Agent Beta Wins"
    elif winner == "Draw":
        css_class, title = "draw", "It's a Draw"
    else:
        return ""  # undecided — handled by vote panel

    return (
        f'<div class="verdict-banner {css_class}">'
        f'  <div class="verdict-title">{_esc(title)}</div>'
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

FORCE_LIGHT_JS = """
function() {
    const removeDark = () => {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
        }
        if (document.body.classList.contains('dark')) {
            document.body.classList.remove('dark');
        }
    };
    removeDark();
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'class') {
                removeDark();
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true });
    observer.observe(document.body, { attributes: true });
}
"""

def build_app() -> gr.Blocks:
    with gr.Blocks(title="Versus AI — Agentic Debater", js=FORCE_LIGHT_JS) as demo:

        # ── Header ────────────────────────────────────────────────────────────
        gr.HTML(
            '<h1 class="title">Versus AI</h1>'
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
            start_btn = gr.Button("Start Debate", variant="primary", scale=1, min_width=160)

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
                '<div class="vote-title">The agents couldn\'t decide — cast your vote</div>'
                '</div>'
            )
            with gr.Row():
                vote_alpha = gr.Button("Agent Alpha Won", variant="primary")
                vote_draw  = gr.Button("Draw")
                vote_beta  = gr.Button("Agent Beta Won", variant="secondary")

        user_verdict_html = gr.HTML(visible=False)

        # ── State holders ─────────────────────────────────────────────────────
        trace_state: gr.State = gr.State(None)

        # ══════════════════════════════════════════════════════════════════════
        # Debate runner (async generator → Gradio streaming)
        # ══════════════════════════════════════════════════════════════════════

        async def run_debate(topic: str):
            if not topic.strip():
                yield (
                    status_bar("idle", "Please enter a debate topic."),
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
                status_bar("active", "Connecting to MCP server and initialising agents…"),
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
                            status_bar("done", f"Debate concluded — {winner} wins"),
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
                            status_bar("done", "No verdict reached — you decide"),
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
                    status_bar("active", f"{turn_label} · {agent_label}…"),
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
                        '<div class="verdict-title">You voted: Agent Alpha Wins</div>'
                        '<div class="verdict-reason">Decided by the audience.</div></div>'
                    )
                elif choice == "Beta":
                    banner = (
                        '<div class="verdict-banner beta-wins">'
                        '<div class="verdict-title">You voted: Agent Beta Wins</div>'
                        '<div class="verdict-reason">Decided by the audience.</div></div>'
                    )
                else:
                    banner = (
                        '<div class="verdict-banner draw">'
                        '<div class="verdict-title">You declared it a Draw</div>'
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
            primary_hue="blue",
            neutral_hue="zinc",
            font=gr.themes.GoogleFont("Inter"),
        ),
    )
