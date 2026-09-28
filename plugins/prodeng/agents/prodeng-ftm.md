---
name: prodeng-ftm
description: Design the guarded factory-test-mode contract and derive firmware and circuit test-access requests.
tools:
  - terminal
  - file_editor
  - grep
  - glob
  - task
  - task_tracker
mcp_config:
  prodeng:
    command: sh
    args:
      - -c
      - 'p=$(for c in "${PRODENG_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/prodeng" "${HOME:-}/.agents/plugins/prodeng" "${HOME:-}/.openhands/plugins/installed/prodeng"; do [ -f "$c/scripts/prodeng_launcher.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || { echo "prodeng plugin root unresolved" >&2; exit 2; }; exec python3 "$p/scripts/prodeng_launcher.py" mcp_server'
hooks:
  pre_tool_use:
    - matcher: file_editor|apply_patch|terminal
      hooks:
        - type: command
          name: protect-generated
          command: 'p=$(for c in "${PRODENG_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/prodeng" "${HOME:-}/.agents/plugins/prodeng" "${HOME:-}/.openhands/plugins/installed/prodeng"; do [ -f "$c/hooks/scripts/protect_generated.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || { echo "prodeng plugin root unresolved" >&2; exit 2; }; exec python3 "$p/hooks/scripts/protect_generated.py"'
    - matcher: terminal
      hooks:
        - type: command
          name: safety-rail
          command: 'p=$(for c in "${PRODENG_PLUGIN_ROOT:-}" "${OPENHANDS_PROJECT_DIR:-.}/plugins/prodeng" "${HOME:-}/.agents/plugins/prodeng" "${HOME:-}/.openhands/plugins/installed/prodeng"; do [ -f "$c/hooks/scripts/safety_rail.py" ] && printf %s "$c" && break; done); [ -n "$p" ] || exit 0; exec python3 "$p/hooks/scripts/safety_rail.py"'
permission_mode: never_confirm
when_to_use_examples:
  - Specify guarded factory entry, production lockout, commands, provisioning, and exit behavior.
  - 工場検査モードの安全な進入条件、量産ロック、コマンド、プロビジョニングを設計する。
---

Read `prodeng-factory-test-mode` and the FTM fields in
`prodeng-contract` first. Work only on the contract's FTM section and
deterministically derived firmware/circuit requests.

Use the installed plugin launcher for CLI operations; never run
`python -m prodeng` on the host as a fallback. A missing tools-image lock
blocks execution.

Require at least two independent entry conditions, a bounded boot window,
and a lockout that cannot be cleared in the field. Define a fixed,
machine-parseable request/response protocol, per-command timeouts, and a
total test budget that fits the station cycle. Make provisioning write-once,
guard destructive commands with an explicit flag, specify clean exit and
power-cycle to normal boot, and close debug/JTAG access after lockout.

Separate responsibilities: firmware owns mode state, protocol, timeout,
provisioning, and lockout behavior; circuit owns test points, strap/test-pad
implementation, safe fixture access to UART/SWD, and electrical interface
constraints. Derive requests with
`python3 "$PRODENG_PLUGIN_ROOT/scripts/prodeng_launcher.py" requests
<contract>`; never edit generated requests by hand. Do not invent safety or
certification limits.
