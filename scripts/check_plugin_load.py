"""Load plugins/prodeng through the OpenHands SDK plugin loader and assert the
expected agents, skills, commands, hooks, and manifest version.

Exits 0 on success and prints a one-line summary; exits 1 listing every
mismatch. Intended for the `plugin-load` CI job.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugins" / "prodeng"

EXPECTED_AGENTS = {
    "prodeng-ftm",
    "prodeng-liaison",
    "prodeng-planner",
    "prodeng-review",
}
EXPECTED_AGENT_MODELS = {
    "prodeng-ftm": "vibebb-author",
    "prodeng-liaison": "vibebb-author",
    "prodeng-planner": "vibebb-author",
    "prodeng-review": "vibebb-review",
}
EXPECTED_AGENT_TOOLS = {
    "prodeng-ftm": {"terminal", "file_editor", "grep", "glob", "task_tracker", "task_tool_set"},
    "prodeng-liaison": {"terminal", "file_editor", "grep", "glob", "task_tracker", "task_tool_set"},
    "prodeng-planner": {"terminal", "file_editor", "grep", "glob", "task_tracker", "task_tool_set"},
    "prodeng-review": {"grep", "glob"},
}
EXPECTED_AGENT_LIMITS = {
    "prodeng-ftm": (30, 3.0),
    "prodeng-liaison": (30, 3.0),
    "prodeng-planner": (40, 3.0),
    "prodeng-review": (24, 3.0),
}
EXPECTED_SKILLS = {
    "prodeng-contract",
    "prodeng-contract-rules",
    "prodeng-dfx",
    "prodeng-factory-test-mode",
    "prodeng-inspection",
    "prodeng-liaison",
    "prodeng-work-instructions",
    "prodeng-workflow",
}
EXPECTED_COMMANDS = {"doctor", "export", "ftm", "gates", "liaison", "plan"}
EXPECTED_SESSION_START_HOOKS = {"prodeng-doctor", "intake-attachments", "ensure-llm-profiles"}
EXPECTED_USER_PROMPT_SUBMIT_HOOKS = {"intake-attachments"}
EXPECTED_PRE_TOOL_USE_HOOKS = {"protect-generated", "safety-rail"}
EXPECTED_STOP_HOOKS = {"report-prodeng-status", "intake-attachments"}
EXPECTED_POST_TOOL_USE_HOOKS = {"record-image-observation", "record-vision-tool-event"}


def _registered_tools() -> set[str]:
    """Import the builtin tool modules so their registrations exist."""
    import openhands.tools.preset.default  # pyright: ignore[reportMissingImports,reportMissingModuleSource]
    from openhands.sdk.tool.registry import (  # pyright: ignore[reportMissingImports,reportMissingModuleSource]
        list_registered_tools,
    )

    openhands.tools.preset.default.register_default_tools(enable_browser=False)
    import openhands.tools.glob.definition  # pyright: ignore[reportMissingImports,reportMissingModuleSource,reportUnusedImport]
    import openhands.tools.grep.definition  # pyright: ignore[reportMissingImports,reportMissingModuleSource,reportUnusedImport]
    import openhands.tools.task.definition  # pyright: ignore[reportMissingImports,reportMissingModuleSource,reportUnusedImport]
    from openhands.sdk.tool.builtins import (  # pyright: ignore[reportMissingImports,reportMissingModuleSource]
        BUILT_IN_TOOL_CLASSES,
    )

    # resolve_tool falls back to BUILT_IN_TOOL_CLASSES for unregistered names.
    return set(list_registered_tools()) | set(BUILT_IN_TOOL_CLASSES)


def _profile_names_from_hook(plugin_dir: Path) -> set[str]:
    hook_path = plugin_dir / "hooks" / "scripts" / "ensure_llm_profiles.py"
    try:
        module = ast.parse(hook_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "_PROFILES"
            for target in statement.targets
        ):
            continue
        if not isinstance(statement.value, (ast.Tuple, ast.List)):
            return set()
        profiles: set[str] = set()
        for element in statement.value.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                return set()
            profiles.add(element.value)
        return profiles
    return set()


def check_plugin(plugin_dir: Path) -> list[str]:
    """Return a list of mismatch reasons (empty means OK)."""
    from openhands.sdk.plugin import (  # pyright: ignore[reportMissingImports,reportMissingModuleSource]
        Plugin,
    )

    reasons: list[str] = []
    try:
        plugin = Plugin.load(plugin_dir)
    except Exception as e:
        return [f"Plugin.load failed: {e}"]

    manifest = json.loads((plugin_dir / ".plugin" / "plugin.json").read_text(encoding="utf-8"))
    if plugin.manifest.version != manifest.get("version"):
        reasons.append(
            f"manifest version {plugin.manifest.version!r} != "
            f"plugin.json {manifest.get('version')!r}"
        )

    agents = {a.name for a in plugin.agents}
    if agents != EXPECTED_AGENTS:
        reasons.append(f"agents {sorted(agents)} != {sorted(EXPECTED_AGENTS)}")
    for agent in plugin.agents:
        expected_tools = EXPECTED_AGENT_TOOLS.get(agent.name)
        actual_tools = set(agent.tools)
        if actual_tools != expected_tools:
            reasons.append(
                f"agent {agent.name!r} tools {sorted(actual_tools)} != "
                f"{sorted(expected_tools or set())}"
            )
        expected_model = EXPECTED_AGENT_MODELS.get(agent.name)
        if agent.model != expected_model:
            reasons.append(f"agent {agent.name!r} model {agent.model!r} != {expected_model!r}")
        expected_limits = EXPECTED_AGENT_LIMITS.get(agent.name)
        if expected_limits is not None:
            expected_iterations, expected_budget = expected_limits
            if (
                agent.max_iteration_per_run != expected_iterations
                or agent.max_budget_per_run != expected_budget
            ):
                reasons.append(
                    f"agent {agent.name!r} limits "
                    f"({agent.max_iteration_per_run}, {agent.max_budget_per_run}) != "
                    f"({expected_iterations}, {expected_budget})"
                )

    profiles = _profile_names_from_hook(plugin_dir)
    missing_profiles = set(EXPECTED_AGENT_MODELS.values()) - profiles
    if missing_profiles:
        reasons.append(f"ensure_llm_profiles.py does not provision {sorted(missing_profiles)}")

    skills = {s.name for s in plugin.skills}
    if skills != EXPECTED_SKILLS:
        reasons.append(f"skills {sorted(skills)} != {sorted(EXPECTED_SKILLS)}")

    commands = {c.name for c in plugin.commands}
    if commands != EXPECTED_COMMANDS:
        reasons.append(f"commands {sorted(commands)} != {sorted(EXPECTED_COMMANDS)}")

    if plugin.hooks is not None:
        collected: dict[str, set[str]] = {
            "session_start": set(),
            "user_prompt_submit": set(),
            "pre_tool_use": set(),
            "stop": set(),
            "post_tool_use": set(),
        }
        for event_name in collected:
            groups: list[Any] = getattr(plugin.hooks, event_name, None) or []
            for group in groups:
                hooks: list[Any] = list(group.hooks)
                names = [h.name for h in hooks if h.name is not None]
                collected[event_name].update(names)
        expected_hooks = {
            "session_start": EXPECTED_SESSION_START_HOOKS,
            "user_prompt_submit": EXPECTED_USER_PROMPT_SUBMIT_HOOKS,
            "pre_tool_use": EXPECTED_PRE_TOOL_USE_HOOKS,
            "stop": EXPECTED_STOP_HOOKS,
            "post_tool_use": EXPECTED_POST_TOOL_USE_HOOKS,
        }
        for event_name, expected in expected_hooks.items():
            if collected[event_name] != expected:
                reasons.append(
                    f"{event_name} hooks {sorted(collected[event_name])} != {sorted(expected)}"
                )
    else:
        reasons.append("plugin hooks are missing")

    for agent in plugin.agents:
        if agent.name == "prodeng-review":
            if agent.mcp_config:
                reasons.append("prodeng-review must not have MCP configuration")
        elif not agent.mcp_config:
            reasons.append(f"agent {agent.name!r} is missing MCP configuration")

    registered = _registered_tools()
    if "task_tool_set" not in registered:
        reasons.append("SDK 1.50.0 registered tool set is missing 'task_tool_set'")
    for agent in plugin.agents:
        for tool in agent.tools:
            if tool not in registered:
                reasons.append(f"agent {agent.name!r} tool {tool!r} not registered")
    for command in plugin.commands:
        for tool in command.allowed_tools:
            if tool not in registered:
                reasons.append(f"command {command.name!r} allowed-tool {tool!r} not registered")

    from prodeng.mcp_server import tool_specs

    for tool in tool_specs():
        description = tool.description
        if not isinstance(description, str) or not description.strip() or "\n" in description:
            reasons.append(f"MCP tool {tool.name!r} must have a one-line description")
        elif description == tool.name.replace("_", " "):
            reasons.append(f"MCP tool {tool.name!r} has a generic name-derived description")
    return reasons


def main() -> int:
    reasons = check_plugin(PLUGIN_DIR)
    if reasons:
        for reason in reasons:
            print(reason)
        return 1
    all_hooks = (
        EXPECTED_SESSION_START_HOOKS
        | EXPECTED_USER_PROMPT_SUBMIT_HOOKS
        | EXPECTED_PRE_TOOL_USE_HOOKS
        | EXPECTED_STOP_HOOKS
        | EXPECTED_POST_TOOL_USE_HOOKS
    )
    print(
        f"plugin-load OK: agents={{{','.join(sorted(EXPECTED_AGENTS))}}} "
        f"skills={{{','.join(sorted(EXPECTED_SKILLS))}}} "
        f"commands={{{','.join(sorted(EXPECTED_COMMANDS))}}} "
        f"hooks={{{','.join(sorted(all_hooks))}}}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
