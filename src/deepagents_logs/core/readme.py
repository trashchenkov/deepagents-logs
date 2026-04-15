from __future__ import annotations

from .state import SessionState


def build_readme(state: SessionState) -> str:
    lines = [
        "# Deep Agents session logs",
        "",
        f"- **Session ID:** {state.session_id}",
        f"- **Started:** {state.started_at}",
        f"- **Stopped:** {state.stopped_at or 'unknown'}",
        f"- **Working directory:** {state.cwd}",
        f"- **Hostname:** {state.hostname}",
        f"- **User:** {state.user}",
    ]
    if state.agent_name:
        lines.append(f"- **Agent:** {state.agent_name}")
    if state.models:
        lines.append(f"- **Models:** {', '.join(sorted(set(state.models)))}")
    lines.extend(
        [
            f"- **Hook events:** {state.hook_events}",
            f"- **Request logs:** {state.request_count}",
            f"- **Response logs:** {state.response_count}",
            "",
            "## User prompts",
        ]
    )
    if not state.prompts:
        lines.append("_No user prompts captured._")
    else:
        for prompt in state.prompts:
            lines.append(f"### {prompt.get('timestamp') or 'unknown'}")
            lines.append("")
            lines.append(str(prompt.get("text") or ""))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
