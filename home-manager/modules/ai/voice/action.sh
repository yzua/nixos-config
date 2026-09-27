#!/usr/bin/env bash
# Toggle a dedicated Voxtype recording and hand its transcript to Pi.

set -euo pipefail

notify() {
  notify-send --app-name="Voice action" "$1" "${2:-}" || true
}

runtime_dir="${XDG_RUNTIME_DIR:?Voice action needs XDG_RUNTIME_DIR}"
transcript_file="$runtime_dir/voxtype-pi-action.txt"
marker_file="$runtime_dir/voxtype-pi-action.active"
lock_file="$runtime_dir/voxtype-pi-action.lock"
state_home="${XDG_STATE_HOME:-${HOME:?}/.local/state}"
session_dir="$state_home/voxtype-pi-action"
session_store="$session_dir/sessions"
session_id_file="$session_dir/session-id"

umask 077
mkdir -p -- "$session_store"
chmod 700 -- "$session_dir" "$session_store"
exec 8>"$session_dir/session.lock"

new_session() {
  local temporary_id
  temporary_id="$(mktemp "$session_dir/session-id.XXXXXX")"
  cat /proc/sys/kernel/random/uuid >"$temporary_id"
  mv -- "$temporary_id" "$session_id_file"
}

if [[ "${1:-toggle}" == reset ]]; then
  flock 8
  new_session
  flock -u 8
  if [[ -e "$marker_file" ]]; then
    case "$(voxtype status)" in
    recording | streaming)
      voxtype record cancel
      rm -f -- "$marker_file" "$transcript_file"
      ;;
    esac
  fi
  notify "Voice action" "Started a new session."
  exit 0
fi
if [[ "${1:-toggle}" != toggle ]]; then
  printf 'usage: voxtype-pi-action [toggle|reset]\n' >&2
  exit 2
fi

exec 9>"$lock_file"
flock -n 9 || exit 0

state="$(voxtype status)"
case "$state" in
idle)
  rm -f -- "$marker_file" "$transcript_file"
  voxtype record start --file="$transcript_file" --no-auto-submit
  : >"$marker_file"
  ;;
recording | streaming)
  if [[ ! -e "$marker_file" ]]; then
    # Keep the old cancel behavior when ordinary Mod+D dictation is active.
    voxtype record cancel
    exit 0
  fi
  flock 8
  if [[ ! -s "$session_id_file" ]]; then
    new_session
  fi
  voice_session_id="$(<"$session_id_file")"
  flock -u 8
  if ! transcript="$(voxtype record stop --wait --timeout 90 --wait-file "$transcript_file")"; then
    rm -f -- "$marker_file" "$transcript_file"
    notify "Voice action" "No usable transcription was produced."
    exit 1
  fi
  rm -f -- "$marker_file"
  if [[ -z "${transcript//[[:space:]]/}" ]]; then
    rm -f -- "$transcript_file"
    exit 0
  fi
  notify "Voice action" "Running your request…"
  if response="$(timeout 120s pi \
    --model codex-lb/gpt-6-luna \
    --thinking low \
    --session "$session_store/$voice_session_id.jsonl" \
    --no-context-files \
    --no-extensions \
    --no-skills \
    --no-prompt-templates \
    --append-system-prompt "${VOICE_ACTION_PROMPT:?}" \
    --print \
    -- "@${transcript_file}" 2>&1)"; then
    notify "Voice action" "${response:0:500}"
  else
    notify "Voice action failed" "${response:0:500}"
    rm -f -- "$transcript_file"
    exit 1
  fi
  rm -f -- "$transcript_file"
  ;;
transcribing)
  notify "Voice action" "Still transcribing the previous recording."
  ;;
*)
  notify "Voice action" "Voxtype is unavailable ($state)."
  exit 1
  ;;
esac
