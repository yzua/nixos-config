# Run OpenRGB with access to only the configured USB HID controllers.
# The caller's normal uaccess ACLs still apply; never elevate privileges.

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/OpenRGB-usb"
mkdir -p -- "$config_dir"
# OpenRGB recognizes only this conventional rule filename, not our equivalent
# 70-* filename. Alias the actual narrow rules only inside the app namespace.
rules_dir=$(realpath -e /etc/udev/rules.d)
scoped_rules="$config_dir/.scoped-udev.rules"
install -m 600 -- "$rules_dir/70-desktop-peripherals.rules" "$scoped_rules"
bindings=()
allowed_devices='@allowedDevices@'

for device in /sys/class/hidraw/hidraw*; do
  [[ -e "$device" ]] || continue
  parent=$(realpath "$device/device")
  while [[ "$parent" == /sys/* ]]; do
    if [[ -r "$parent/idVendor" && -r "$parent/idProduct" ]]; then
      vendor=$(<"$parent/idVendor")
      product=$(<"$parent/idProduct")
      if [[ "|$allowed_devices|" == *"|$vendor:$product|"* ]]; then
        node="/dev/${device##*/}"
        if [[ ! -r "$node" || ! -w "$node" ]]; then
          printf 'USB lighting access missing for %s; refresh the NixOS udev rules.\n' "$node" >&2
          exit 1
        fi
        bindings+=(--dev-bind "$node" "$node")
      fi
      break
    fi
    parent=${parent%/*}
  done
done

if [[ ${#bindings[@]} -eq 0 ]]; then
  printf 'No configured USB lighting controllers are connected.\n' >&2
  exit 1
fi

# A fresh /dev hides every other HID, USB-bus, I2C, memory and GPU device.
# A private /proc prevents reaching the host's /dev through another PID.
# Only this app's mutable settings directory is writable in the home directory.
# Software rendering avoids granting GPU device access just to draw this GUI.
# Serialize with login restoration; hold this lock until OpenRGB exits.
exec flock --nonblock "$XDG_RUNTIME_DIR/usb-lighting.lock" bwrap \
  --ro-bind / / \
  --dev /dev \
  --proc /proc \
  --unshare-all \
  --die-with-parent \
  --new-session \
  --tmpfs /tmp \
  --ro-bind-try /tmp/.X11-unix /tmp/.X11-unix \
  --tmpfs "$rules_dir" \
  --ro-bind "$scoped_rules" "$rules_dir/60-openrgb.rules" \
  --bind "$config_dir" "$config_dir" \
  --setenv LIBGL_ALWAYS_SOFTWARE 1 \
  "${bindings[@]}" \
  -- @openrgb@ --config "$config_dir" --noautoconnect "$@"
