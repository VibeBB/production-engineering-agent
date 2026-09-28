from __future__ import annotations

import ast
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, TextIO

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
    process = subprocess.Popen(
        [sys.executable, "-m", "prodeng.mcp_server"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdin = process.stdin
    stdout = process.stdout
    stderr = process.stderr
    assert stdin is not None
    assert stdout is not None
    assert stderr is not None

    output_lines: queue.Queue[str | None] = queue.Queue()
    stderr_lines: list[str] = []
    stderr_lock = threading.Lock()

    def enqueue_stdout(stream: TextIO) -> None:
        for line in stream:
            output_lines.put(line)
        output_lines.put(None)

    def capture_stderr(stream: TextIO) -> None:
        for line in stream:
            with stderr_lock:
                stderr_lines.append(line)

    def stderr_output() -> str:
        with stderr_lock:
            return "".join(stderr_lines).strip() or "<empty>"

    stdout_thread = threading.Thread(target=enqueue_stdout, args=(process.stdout,), daemon=True)
    stderr_thread = threading.Thread(target=capture_stderr, args=(process.stderr,), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    deadline = time.monotonic() + 30

    def read_response(expected_id: int) -> dict[str, Any]:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"Timed out waiting for JSON-RPC id {expected_id}; stderr: {stderr_output()}"
                )
            try:
                line = output_lines.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError(
                    f"Timed out waiting for JSON-RPC id {expected_id}; stderr: {stderr_output()}"
                ) from None
            if line is None:
                raise AssertionError(
                    f"MCP server closed stdout before JSON-RPC id {expected_id}; "
                    f"stderr: {stderr_output()}"
                )
            if line.strip():
                response = json.loads(line)
                if response.get("id") == expected_id:
                    return response

    try:
        stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "prodeng-entrypoint-test",
                            "version": "1.0",
                        },
                    },
                }
            )
            + "\n"
        )
        stdin.flush()
        initialize_response = read_response(1)
        assert "result" in initialize_response, initialize_response

        stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        tools_list_request: dict[str, object] = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        stdin.write(json.dumps(tools_list_request) + "\n")
        stdin.flush()
        tools_response = read_response(2)
        tools = tools_response["result"]["tools"]
        tool_names = {tool["name"] for tool in tools}
        assert tool_names >= EXPECTED_TOOLS

        stdin.close()
        try:
            return_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(
                f"MCP server did not exit after stdin closed; stderr: {stderr_output()}"
            ) from exc
        assert return_code == 0, stderr_output()
    finally:
        if not stdin.closed:
            stdin.close()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)


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
