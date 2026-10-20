#!/usr/bin/env bash
# Stop hook for pi-spawned Claude sessions.
# Writes a sentinel file when Claude completes autonomously (no user interjection).

set -euo pipefail

# Read JSON input from stdin
input=$(cat)

# Guard: if stop_hook_active is true, we're in a loop — bail out
stop_hook_active=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stop_hook_active', False))" 2>/dev/null || echo "False")
if [ "$stop_hook_active" = "True" ]; then
  exit 0
fi

# Guard: only act for pi-spawned sessions
if [ -z "${PI_CLAUDE_SENTINEL:-}" ]; then
  exit 0
fi

# Get transcript path
transcript_path=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('transcript_path', ''))" 2>/dev/null || echo "")
if [ -z "$transcript_path" ] || [ ! -f "$transcript_path" ]; then
  exit 0
fi

# Count real human messages in transcript (not tool results)
# Claude's transcript format:
#   Human message: {"type": "user", "message": {"role": "user", "content": "..."}}
#   Tool result:   {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", ...}]}}
# We only count entries where content is a string (real human input)
user_msg_count=$(
  python3 - "$transcript_path" <<'EOF'
import sys, json

transcript_path = sys.argv[1]
count = 0
with open(transcript_path, 'r') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get('type') != 'user':
                continue
            content = entry.get('message', {}).get('content', '')
            # Real human messages have string content
            # Tool results have array content with tool_result blocks
            if isinstance(content, str):
                count += 1
        except (json.JSONDecodeError, AttributeError):
            pass
print(count)
EOF
)

# Always write transcript path so the watcher can copy the session file
if [ -n "$transcript_path" ]; then
  echo "$transcript_path" >"${PI_CLAUDE_SENTINEL}.transcript" 2>/dev/null || true
fi

# If exactly 1 user message (the initial prompt), this was autonomous — signal completion
if [ "$user_msg_count" -eq 1 ]; then
  # Write last_assistant_message to sentinel so the watcher gets a clean result
  echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('last_assistant_message', ''))" >"$PI_CLAUDE_SENTINEL" 2>/dev/null || touch "$PI_CLAUDE_SENTINEL"
fi

exit 0
