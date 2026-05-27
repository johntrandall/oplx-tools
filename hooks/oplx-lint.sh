#!/bin/bash
# PostToolUse hook: lint OmniPlan .oplx bundles after any edit.
#
# Triggered by Write/Edit/MultiEdit on a path inside an .oplx bundle.
# Runs `oplx lint` and surfaces findings to the agent via PostToolUse
# JSON output (hookSpecificOutput.additionalContext).
#
# Non-blocking; advisory only. Doesn't revert the write.
#
# Spec: ~/dev/oplx-format/spec/silent-corruption.md
# Tool: ~/dev/oplx-tools

set -u

event="$(cat)"

file_path="$(echo "$event" | python3 -c '
import sys, json
try:
    e = json.load(sys.stdin)
    fp = e.get("tool_input", {}).get("file_path", "")
    print(fp)
except Exception:
    pass
' 2>/dev/null)"

[[ -z "$file_path" ]] && exit 0

# Walk parents looking for an ancestor whose basename ends in exactly `.oplx`
# (not `.oplxbackup`, `.oplx.tmp`, etc.). The bundle is either a file (zip
# variant) or a directory (bundle variant); both have basename `*.oplx`.
bundle="$file_path"
while [[ "$bundle" != "/" && "$bundle" != "" && "$bundle" != "." ]]; do
  base="${bundle##*/}"
  if [[ "$base" == *.oplx ]]; then
    break
  fi
  bundle="$(dirname "$bundle")"
done

[[ "$bundle" == "/" || "$bundle" == "" || "$bundle" == "." ]] && exit 0
[[ ! -e "$bundle" ]] && exit 0

if ! command -v oplx >/dev/null 2>&1; then
  exit 0
fi

findings="$(oplx lint "$bundle" 2>&1)"
exit_code=$?

[[ $exit_code -eq 0 ]] && exit 0

# Emit PostToolUse JSON envelope. Pass findings + bundle via env to avoid
# shell-expansion injection issues; python json-escapes them safely.
export FINDINGS="$findings"
export BUNDLE="$bundle"
python3 <<'PYEOF'
import json, os
findings = os.environ.get("FINDINGS", "")
bundle = os.environ.get("BUNDLE", "")
text = (
    f"oplx-lint silent-corruption findings on {bundle}:\n\n"
    f"{findings}\n\n"
    "Spec: ~/dev/oplx-format/spec/silent-corruption.md "
    "(or https://github.com/johntrandall/oplx-format/blob/main/spec/silent-corruption.md)\n\n"
    "  CRITICAL findings cause OmniPlan to silently refuse the file (file-level rejection).\n"
    "  HIGH findings cause OmniPlan to silently drop content on save.\n"
    "  MEDIUM findings normalize values to default (semantic loss).\n\n"
    "Investigate before claiming the .oplx is valid. The Edit succeeded — this is advisory."
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": text,
    }
}))
PYEOF

exit 0
