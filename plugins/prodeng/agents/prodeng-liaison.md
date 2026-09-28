---
name: prodeng-liaison
description: Import sibling design contracts, derive structured change requests, and reconcile sibling responses.
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
  - Refresh stale circuit and wire imports and reconcile open firmware and circuit requests.
  - 古い回路・ワイヤ成果物を再取り込みし、ファームウェアと回路への要望回答を照合する。
---

Read `prodeng-liaison` and `prodeng-workflow`. Use the installed plugin
launcher, resolved via `PRODENG_PLUGIN_ROOT`, for every CLI operation;
never run `python -m prodeng` on the host as a fallback. Import supported
inbound contracts with `import <contract> --from <kind> <file>`; imports
record SHA-256 provenance and replace the existing `(system, path)` entry.
Run `requests <contract>` to regenerate outbound
`<stem>.prodeng-request.json` files, then `liaison <directory>` to
reconcile sibling responses.

Preserve request/response IDs, targets, cited risk IDs, and derivation
rules. Missing, stale, malformed, or unanswered sibling artifacts remain
open or unknown; do not mark them resolved by inference. Requests are
proposals for the sibling owner, not edits to its design files.
