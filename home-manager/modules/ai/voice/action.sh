#!/usr/bin/env bash
# Own shared Voxtype recording commands and hand action transcripts to Pi.

set -euo pipefail
umask 077

notify() {
  notify-send --app-name="Voice action" "$1" "${2:-}" || true
}

command="${1:-toggle}"
case "$command" in
toggle | reset | dictation-toggle | cancel) ;;
*)
  printf 'usage: voxtype-pi-action [toggle|reset|dictation-toggle|cancel]\n' >&2
  exit 2
  ;;
esac

runtime_dir="${XDG_RUNTIME_DIR:?Voice action needs XDG_RUNTIME_DIR}/voxtype-pi-action"
state_home="${XDG_STATE_HOME:-${HOME:?}/.local/state}"
session_dir="$state_home/voxtype-pi-action"
session_store="$session_dir/sessions"
session_id_file="$session_dir/session-id"
owner_file="$runtime_dir/owner"
mkdir -p -- "$runtime_dir" "$session_store"
chmod 700 -- "$runtime_dir" "$session_dir" "$session_store"

# Control serializes recording mutations, ownership, and session selection.
# Work excludes a second action while waiting for transcription or executing Pi;
# reset/cancel never need it. Only the submitted request supervisor inherits work;
# Pi and its tools inherit neither lock, and no long-running child holds control.
exec 8>"$runtime_dir/control.lock"
exec 9>"$runtime_dir/work.lock"
flock 8

new_session() {
  local temporary_id
  temporary_id="$(mktemp "$session_dir/session-id.XXXXXX")"
  cat /proc/sys/kernel/random/uuid >"$temporary_id"
  mv -- "$temporary_id" "$session_id_file"
}

owned_job() {
  if [[ -s "$owner_file" ]]; then
    printf '%s/%s' "$runtime_dir" "$(<"$owner_file")"
  fi
}

# Voxtype commands signal the daemon asynchronously. Keep control until it has
# acknowledged the mutation, so rapid shortcuts cannot target the old recording.
await_state() {
  local expected="$1" state attempt
  for ((attempt = 0; attempt < 100; attempt++)); do
    state="$(voxtype status)" || return 1
    case "$expected:$state" in
    idle:idle | active:recording | active:streaming | stopped:transcribing | stopped:idle) return 0 ;;
    esac
    if [[ "$expected" == stopped && -n "${waiter:-}" && -z "$(jobs -pr)" ]]; then
      # The wait CLI can finish after this status snapshot was read. Its result
      # is stronger acknowledgement; handle success/failure after wait below.
      return 0
    fi
    sleep 0.05
  done
  notify "Voice action" "Voxtype did not acknowledge the recording command."
  return 1
}

cancel_recording() {
  local state
  state="$(voxtype status)" || return 1
  case "$state" in
  recording | streaming | transcribing)
    voxtype record cancel && await_state idle
    ;;
  idle) ;;
  *) return 1 ;;
  esac
}

discard_pending() {
  local pending phase
  pending="$(owned_job)"
  [[ -n "$pending" ]] || return 0
  phase="$(<"$pending/phase")"
  [[ "$phase" != submitted && ! -e "$pending/cancelled" ]] || return 0
  # Invalidate before cancelling: even a failed cancel must never submit this job.
  # Retain its identity on failure so the next command can retry cancellation and
  # cleanup rather than mistake the daemon's remaining recording for dictation.
  printf 'discarded\n' >"$pending/phase"
  cancel_recording || return 1
  : >"$pending/cancelled"
  if [[ ! -e "$pending/worker" ]]; then
    rm -f -- "$owner_file"
    rm -rf -- "$pending"
  fi
}

# Called with both locks: no request worker/supervisor can still own these files.
# A recording has no live worker by design; an orphaned decode must be discarded
# rather than submitted, and must retain ownership until the daemon settles.
reconcile_finished_owner() {
  local pending phase
  pending="$(owned_job)"
  [[ -n "$pending" ]] || return 0
  phase="$(<"$pending/phase")"
  case "$phase" in
  submitted)
    rm -f -- "$owner_file"
    rm -rf -- "$pending"
    ;;
  transcribing | discarded)
    printf 'discarded\n' >"$pending/phase"
    rm -f -- "$pending/worker"
    if [[ -e "$pending/cancelled" ]]; then
      rm -f -- "$owner_file"
      rm -rf -- "$pending"
    fi
    ;;
  esac
}

# Reset/cancel can reconcile a finished orphan without ever waiting for work.
if flock -n 9; then
  reconcile_finished_owner
  flock -u 9
fi

if [[ "$command" == reset ]]; then
  new_session
  discard_pending
  notify "Voice action" "Started a new session."
  exit 0
fi
if [[ "$command" == cancel ]]; then
  discard_pending
  cancel_recording
  exit 0
fi
if [[ "$command" == dictation-toggle ]]; then
  pending="$(owned_job)"
  if [[ -n "$pending" && "$(<"$pending/phase")" != submitted && ! -e "$pending/cancelled" ]]; then
    discard_pending
  else
    state="$(voxtype status)"
    voxtype record toggle
    case "$state" in
    idle) await_state active ;;
    recording | streaming) await_state stopped ;;
    esac
  fi
  exit 0
fi

flock -n 9 || exit 0
# Work may have ended between the nonblocking check above and this acquisition.
reconcile_finished_owner
state="$(voxtype status)"
job="$(owned_job)"
case "$state" in
idle)
  # A daemon-side stop/cancel may have ended an abandoned action recording.
  discard_pending
  if [[ ! -s "$session_id_file" ]]; then
    new_session
  fi
  job="$(mktemp -d "$runtime_dir/request.XXXXXX")"
  transcript_file="$job/transcript.txt"
  : >"$transcript_file"
  printf 'recording\n' >"$job/phase"
  cp -- "$session_id_file" "$job/session-id"
  if ! voxtype record start --file="$transcript_file" --no-auto-submit; then
    rm -rf -- "$job"
    notify "Voice action" "Could not start recording."
    exit 1
  fi
  printf '%s\n' "${job##*/}" >"$owner_file"
  await_state active
  exit 0
  ;;
recording | streaming | transcribing)
  if [[ -z "$job" ]]; then
    # Ordinary dictation keeps its paste output, including an in-flight decode.
    if [[ "$state" == transcribing ]]; then
      notify "Voice action" "Still transcribing the previous recording."
    else
      cancel_recording
    fi
    exit 0
  fi
  if [[ "$(<"$job/phase")" == discarded ]]; then
    discard_pending
    exit 0
  fi
  ;;
*)
  notify "Voice action" "Voxtype is unavailable ($state)."
  exit 1
  ;;
esac

# Each request has private files. A live worker owns cleanup; finished orphans
# are reconciled above. Executing Pi keeps its attachment until it has finished.
cleanup() {
  flock 8
  rm -f -- "$job/worker"
  if [[ "$(<"$job/phase")" == submitted && ! -e "$job/pi-status" ]]; then
    # TERM/EXIT can run while the child survives. It still needs the attachment.
    return
  fi
  if [[ "$(owned_job)" == "$job" ]]; then
    if [[ "$(<"$job/phase")" != submitted && ! -e "$job/cancelled" ]]; then
      # The transcription CLI may be gone while the daemon is still decoding.
      # Keep discarded ownership until completion/cancellation is confirmed;
      # otherwise its output can reappear without an owner after cleanup.
      printf 'discarded\n' >"$job/phase"
      [[ "$(voxtype status)" == idle ]] || return 0
    fi
    rm -f -- "$owner_file"
  fi
  rm -rf -- "$job"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
transcript_file="$job/transcript.txt"
voice_session_id="$(<"$job/session-id")"
printf 'transcribing\n' >"$job/phase"
: >"$job/worker"
voxtype record stop --wait --timeout 90 --wait-file "$transcript_file" >"$job/text" 8>&- 9>&- &
waiter=$!
if ! await_state stopped; then
  discard_pending
  kill %1 2>/dev/null || true
  wait "$waiter" 2>/dev/null || true
  notify "Voice action" "No usable transcription was produced."
  exit 1
fi
flock -u 8
# Cancellation is cooperative with the worker. Only the parent shell can signal
# its own transcription job, using its job table (not a persisted, reusable PID).
# No other background job exists here, and this path never signals executing Pi.
while [[ -n "$(jobs -pr)" ]]; do
  flock 8
  if [[ "$(owned_job)" != "$job" || "$(<"$job/phase")" != transcribing ]]; then
    kill %1 2>/dev/null || true
    flock -u 8
    break
  fi
  flock -u 8
  sleep 0.05 8>&- 9>&-
done
transcription_status=0
wait "$waiter" || transcription_status=$?
flock 8
# Reset/cancel linearizes against submission here, not against daemon status.
[[ "$(owned_job)" == "$job" && "$(<"$job/phase")" == transcribing ]] || exit 0
if ((transcription_status != 0)); then
  discard_pending
  notify "Voice action" "No usable transcription was produced."
  exit 1
fi
transcript="$(<"$job/text")"
if [[ -z "${transcript//[[:space:]]/}" ]]; then
  exit 0
fi

notify "Voice action" "Running your request…"
printf 'submitted\n' >"$job/phase"
# Submission happens under control. Reset after this point selects a new session
# but cannot revoke this request, kill Pi, or unlink its transcript.
(
  trap - EXIT TERM INT
  # Keep work locked for the whole submitted request, independently of the
  # wrapper's lifetime. Close it for Pi so spawned apps cannot prolong busy.
  pi_status=0
  timeout 120s pi \
    --model codex-lb/gpt-6-luna \
    --thinking low \
    --session "$session_store/$voice_session_id.jsonl" \
    --no-context-files \
    --no-extensions \
    --no-skills \
    --no-prompt-templates \
    --append-system-prompt "${VOICE_ACTION_PROMPT:?}" \
    --print \
    -- "@${transcript_file}" >"$job/response" 2>&1 9>&- || pi_status=$?
  printf '%s\n' "$pi_status" >"$job/pi-status"
  exit "$pi_status"
) 8>&- &
pi_pid=$!
flock -u 8
pi_status=0
wait "$pi_pid" || pi_status=$?
response="$(<"$job/response")"
if ((pi_status == 0)); then
  notify "Voice action" "${response:0:500}"
else
  notify "Voice action failed" "${response:0:500}"
  exit 1
fi
