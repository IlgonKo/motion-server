# Independent session permission check — 2026-09-11

## Confirmed

- CLI 0.153.4; prior invocation with --ignore-user-config and --sandbox workspace-write resolved to read-only.
- Adding invocation-only `-c windows.sandbox="elevated"` resolves to workspace-write.
- Read input.txt succeeded; apply_patch created output.txt; parent independently read the expected content.
- Bare python was not found in sandbox PATH.
- Explicit installed interpreter `C:/Users/Festo/AppData/Local/Python/pythoncore-3.14-64/python.exe`
  was attempted once and Windows denied process creation (PowerShell exit 1). Python did not run.
- Therefore the remaining issue is not only PATH. Exact ACL/policy source is not established.

## Scope

Global config/ACLs were not edited. No sandbox bypass, fallback to full access, alternate Python runtime,
or administrator setup was attempted. No Motion Server, hardware or Node-RED test ran.

## Next prerequisite

Use a supported sandbox read-access grant for the interpreter installation and verify execution.
Official documentation describes `/sandbox-add-read-dir` for an existing absolute directory;
this is a session action, not a PowerShell command. An explicit directory grant is preferable to
loosening global user-folder ACLs. If access remains denied, inspect native sandbox setup/policy.

Reference: https://learn.chatgpt.com/docs/windows/windows-sandbox
Logs: events-elevated.jsonl / stderr-elevated.txt / events-python.jsonl / stderr-python.txt.
