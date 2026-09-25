#!/usr/bin/env bash
#
# One-time activation: point /etc/nixos at ~/System, then rebuild.
#
#   sudo ~/System/activate.sh          # rebuild with "switch" (applies now)
#   sudo ~/System/activate.sh test     # rebuild with "test" (applies after reboot)
#
# Why this exists: NixOS only ever reads its configuration from /etc/nixos.
# That directory is root-owned, so it cannot be edited without sudo. Making it a
# symlink to ~/System means the real files live in your home directory, where
# they are yours to edit, while nixos-rebuild keeps working unchanged.
#
# After this has run once, editing ~/System/configuration.nix needs no sudo at
# all -- only `sudo nixos-rebuild switch` does.

set -euo pipefail

SRC="/home/yz/System"   # absolute on purpose: $HOME is /root under sudo
DST="/etc/nixos"
ACTION="${1:-switch}"

die() { echo "error: $*" >&2; exit 1; }

# --- sanity checks -----------------------------------------------------------

[ "$(id -u)" -eq 0 ] || die "run this with sudo"
[ "$ACTION" = "switch" ] || [ "$ACTION" = "test" ] \
  || die "action must be 'switch' or 'test', got '$ACTION'"

[ -f "$SRC/configuration.nix" ] || die "missing $SRC/configuration.nix"
[ -f "$SRC/hardware-configuration.nix" ] || die "missing $SRC/hardware-configuration.nix"

# --- swap the directory for a symlink ---------------------------------------

if [ -L "$DST" ]; then
  echo "==> $DST is already a symlink -> $(readlink "$DST")"
  [ "$(readlink -f "$DST")" = "$(readlink -f "$SRC")" ] \
    || die "$DST points somewhere else; fix it by hand"
elif [ -d "$DST" ]; then
  echo "==> comparing $DST with $SRC"
  if diff -rq "$DST" "$SRC" >/dev/null 2>&1; then
    echo "    contents are identical"
  else
    echo "    differences (expected: configuration.nix was edited):"
    diff -rq "$DST" "$SRC" | sed 's/^/      /'
  fi

  BACKUP="${DST}.bak.$(date +%Y%m%d-%H%M%S)"
  mv "$DST" "$BACKUP"
  echo "    old directory backed up to $BACKUP"
  ln -s "$SRC" "$DST"
  echo "==> $DST -> $SRC"
else
  ln -s "$SRC" "$DST"
  echo "==> created $DST -> $SRC"
fi

# --- rebuild -----------------------------------------------------------------

echo "==> nixos-rebuild $ACTION (this may take a while)"
nixos-rebuild "$ACTION"

cat <<'EOF'

==> done.

  Log out and back in (or reboot) for the input sources to be applied.
  GNOME will now have two layouts: English (default) and Arabic.
  Switch between them with Super+Space.

  Dates and numbers are English/Gregorian again.

  From now on: edit ~/System/configuration.nix freely, then run
      sudo nixos-rebuild switch
EOF
