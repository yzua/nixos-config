# Shared helpers for NixOS modules.
#
# These are _-prefixed helper files, imported manually by consumers.
# Do NOT add them to imports — modules-check enforces this convention.
#
# Available helpers:
#   _systemd-helpers.nix  — mkServiceHardening, mkNixosTimer, mkOneshotService
#
# Service URLs are now `constants.urls` (auto-derived from constants.ports).
#
# Usage (from a sibling module):
#   inherit (systemdHelpers) mkNixosTimer;
#   inherit (constants) urls;

{ }
