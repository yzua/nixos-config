# Toggle writing assistance without guessing the user's previous input engine.
# shellcheck shell=bash
state_file="${XDG_RUNTIME_DIR:?}/typing-booster-previous-engine"
# Serialize distinct key presses as well as suppressing key repeat in Niri.
exec 9>"$XDG_RUNTIME_DIR/typing-booster.lock"
flock 9
current="$(ibus engine)"

if [[ "$current" == typing-booster ]]; then
  if [[ ! -s "$state_file" ]]; then
    echo "Previous input engine unknown; select a plain layout in IBus preferences." >&2
    exit 1
  fi
  IFS= read -r previous <"$state_file"
  ibus engine "$previous"
  rm -f -- "$state_file"
else
  printf '%s\n' "$current" >"$state_file"
  ibus engine typing-booster
fi
