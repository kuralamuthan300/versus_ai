"""
main.py — Entry point for Versus AI.

Usage:
    # Launch Gradio UI (default)
    uv run main.py

    # CLI headless mode
    uv run main.py --cli "AI will replace all software engineers by 2030"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# ── resolve src package path ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "versus_ai"))


def _cli_mode(topic: str) -> None:
    from agent import debate_loop
    from data_models import AgentTrace, Event

    async def run():
        print(f"\n{'═'*60}")
        print(f"  VERSUS AI — Headless Debate")
        print(f"  Topic: {topic}")
        print(f"{'═'*60}\n")

        async for item in debate_loop(topic):
            if isinstance(item, AgentTrace):
                print(f"\n{'─'*60}")
                print("  FULL TRACE SUMMARY")
                print(f"{'─'*60}")
                print(f"  Goal      : {item.goal}")
                print(f"  Events    : {len(item.events)}")
                duration = max(e.timestamp for e in item.events) - item.started_at
                print(f"  Duration  : {duration:.1f}s")
                continue

            evt: Event = item
            if evt.kind == "llm_call":
                side = "🔵 ALPHA" if "alpha" in evt.agent_name.lower() else "🔴 BETA "
                print(f"\n[Turn {evt.turn}] {side} — {evt.agent_name}")
                print(f"  💭 {evt.agent_thought}")
                print(f"  📢 {evt.payload.get('argument', '')}")
                tcs = evt.payload.get("tool_calls", [])
                if tcs:
                    print(f"  🔧 Requesting tools: {[tc['name'] for tc in tcs]}")
            elif evt.kind == "tool_call":
                print(f"     ⚙  {evt.tool_name} → {json.dumps(evt.tool_result)[:120]}…")
            elif evt.kind == "verdict":
                winner = evt.payload.get("winner")
                print(f"\n{'═'*60}")
                if winner:
                    print(f"  🏆 WINNER: {winner}")
                    print(f"  Reason: {evt.payload.get('reason', '')}")
                else:
                    print("  🤔 No verdict — needs human judgement.")
                print(f"{'═'*60}\n")

    asyncio.run(run())


def _ui_mode() -> None:
    import gradio as gr
    from app import build_app, CSS
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Versus AI — Agentic Debater")
    parser.add_argument(
        "--cli",
        metavar="TOPIC",
        help="Run headless CLI debate on the given topic.",
    )
    args = parser.parse_args()

    if args.cli:
        _cli_mode(args.cli)
    else:
        _ui_mode()


if __name__ == "__main__":
    main()
