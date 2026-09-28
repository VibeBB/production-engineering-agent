from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "prodeng_doctor",
    "prodeng_validate",
    "prodeng_gates",
    "prodeng_export",
    "prodeng_author",
    "prodeng_import",
    "prodeng_requests",
    "prodeng_liaison",
    "prodeng_sample",
}


def test_cli_doctor_module_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prodeng.cli", "doctor"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
    assert json.loads(result.stdout)["verdict"] == "pass"


def test_cli_validate_module_entrypoint() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "prodeng.cli",
            "validate",
            "examples/smart-kettle/smart-kettle.prodeng.json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
    assert json.loads(result.stdout)["verdict"] == "pass"


def test_mcp_server_module_entrypoint() -> None:
    messages: list[dict[str, object]] = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "prodeng-entrypoint-test", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    result = subprocess.run(
        [sys.executable, "-m", "prodeng.mcp_server"],
        cwd=ROOT,
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    tools_response = next(response for response in responses if response.get("id") == 2)
    tools = tools_response["result"]["tools"]
    tool_names = {tool["name"] for tool in tools}
    assert tool_names >= EXPECTED_TOOLS


def test_launcher_module_targets_have_main_guards() -> None:
    launcher_path = ROOT / "plugins/prodeng/scripts/prodeng_launcher.py"
    launcher_source = launcher_path.read_text(encoding="utf-8")
    module_map_match = re.search(r"_MODULES\s*=\s*\{(?P<body>.*?)\}", launcher_source, re.DOTALL)
    assert module_map_match is not None

    module_pairs = re.findall(
        r"""["']([^"']+)["']\s*:\s*["']([^"']+)["']""",
        module_map_match.group("body"),
    )
    module_names = {"prodeng.cli", *(module for _, module in module_pairs)}
    assert module_pairs

    for module_name in module_names:
        module_path = ROOT / "src" / Path(*module_name.split(".")).with_suffix(".py")
        module_tree = ast.parse(module_path.read_text(encoding="utf-8"))
        has_main_guard = any(
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Eq)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "__main__"
            for node in module_tree.body
        )
        assert has_main_guard, f"{module_name} has no __main__ guard"
