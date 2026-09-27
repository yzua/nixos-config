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
    --no-session \
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
