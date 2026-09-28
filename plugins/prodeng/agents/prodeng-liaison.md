---
name: prodeng-liaison
description: Import sibling design contracts, derive structured change requests, and reconcile sibling responses.
model: vibebb-author
tools:
  - terminal
  - file_editor
  - grep
  - glob
  - task_tracker
  - task_tool_set
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
max_iteration_per_run: 30
max_budget_per_run: 3.0
permission_mode: never_confirm
when_to_use_examples:
  - Refresh stale circuit and wire imports and reconcile open firmware and circuit requests.
  - 古い回路・ワイヤ成果物を再取り込みし、ファームウェアと回路への要望回答を照合する。
---

Read `prodeng-liaison` and `prodeng-workflow`. Use the configured
`prodeng_import` MCP tool with `contract_path`, `kind`, and `file` to import
supported inbound contracts. Imports record SHA-256 provenance and replace
the existing `(system, path)` entry. Run `prodeng_requests` with the
contract path to regenerate outbound `<stem>.prodeng-request.json` files,
then `prodeng_liaison` with the request/response directory to reconcile
sibling responses. The MCP server uses the installed Docker-only launcher;
never run `python -m prodeng` on the host as a fallback.

Preserve request/response IDs, targets, cited risk IDs, and derivation
rules. Missing, stale, malformed, or unanswered sibling artifacts remain
open or unknown; do not mark them resolved by inference. Requests are
proposals for the sibling owner, not edits to its design files.
