#!/bin/bash
# PostToolUse hook: lint OmniPlan .oplx bundles after any edit.
#
# Triggered by Write/Edit/MultiEdit on a path that resolves to inside an
# .oplx directory bundle (Actual.xml, __TOC.xml, __changelog.xml, or any
# file inside a *.oplx/ directory). Runs `oplx lint` against the bundle
# and emits findings to stderr so the agent sees them in the next turn.
#
# This is a NON-BLOCKING hook (exits 0 even when findings exist) — its
# purpose is to alert the agent so it can self-correct, not to fail the
# write. Agents finding CRITICAL/HIGH findings should investigate before
# claiming the .oplx is valid.
#
# Spec: ~/dev/oplx-format/spec/silent-corruption.md
# Tool: ~/dev/oplx-tools

set -u

# Read JSON event from stdin
event="$(cat)"

# Extract the file_path from the tool input (JSON parse without jq dep)
# Hook events look like: {"tool_input": {"file_path": "/path/to/file.xml"}, ...}
file_path="$(echo "$event" | python3 -c '
import sys, json
try:
    e = json.load(sys.stdin)
    fp = e.get("tool_input", {}).get("file_path", "")
    print(fp)
except Exception:
    pass
' 2>/dev/null)"

# Bail if no path or no .oplx in path
[[ -z "$file_path" ]] && exit 0
[[ "$file_path" != *".oplx"* ]] && exit 0

# Find the .oplx bundle root by walking up
bundle="$file_path"
while [[ "$bundle" != "/" && "$bundle" != "" ]]; do
  if [[ "$bundle" == *.oplx ]]; then
    break
  fi
  bundle="$(dirname "$bundle")"
done

[[ "$bundle" == "/" || "$bundle" == "" ]] && exit 0
[[ ! -e "$bundle" ]] && exit 0

# Skip if oplx CLI isn't installed
if ! command -v oplx >/dev/null 2>&1; then
  exit 0
fi

# Run the linter; capture findings
findings="$(oplx lint "$bundle" 2>&1)"
exit_code=$?

# If no blocker-level findings, stay quiet
if [[ $exit_code -eq 0 ]]; then
  exit 0
fi

# Emit findings to stderr (the agent will see this in the tool result)
{
  echo ""
  echo "════════════════════════════════════════════════════════════════"
  echo "  oplx-lint: silent-corruption findings in $bundle"
  echo "════════════════════════════════════════════════════════════════"
  echo "$findings"
  echo "────────────────────────────────────────────────────────────────"
  echo "  Spec: ~/dev/oplx-format/spec/silent-corruption.md"
  echo "  CRITICAL findings cause OmniPlan to silently refuse the file."
  echo "  HIGH findings cause OmniPlan to silently drop content on save."
  echo "════════════════════════════════════════════════════════════════"
} >&2

# Non-blocking — exit 0 so the write itself isn't reverted
exit 0
