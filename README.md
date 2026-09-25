# NixOS configuration

The `nixos` flake output imports `configuration.nix`, which imports this
machine's `hardware-configuration.nix`. The lock file pins Nixpkgs and Home
Manager to the matching 26.05 release branches. No old machine configuration
or Home Manager modules are imported.

This is a fresh Git repository with no remote. The `just` commands use its
tracked files as the flake source; run `git add` when creating a new Nix file,
or Nix will not see it.

From `~/System`, run `just verify` to evaluate, `just build` to build without
activation, and `just preview` to build and compare with the running system.
Only `just switch` activates the last built closure. It refuses a stale build,
so preview again after making changes.

Home Manager is standalone and separate from the NixOS switch. `yz@nixos` is in
`home-manager/home.nix`: Telegram and GNOME's English/Arabic input sources live
there. Node.js/npm stay in NixOS system packages for all users, including root.
Home Manager does not manage your
shell or Firefox settings. Run `just home-preview` to build it; `just
home-switch` activates it as `yz` without sudo, but only after checking that
the built home configuration is current. It also writes the GNOME input-source
dconf setting (not a managed file shown by the preview). `just verify` evaluates
both NixOS and Home Manager.

For this migration, activate Home Manager **before** switching NixOS: `just
home-preview`, `just home-switch`, `just preview`, then `just switch`. This
keeps Telegram available while moving Node.js into system packages, drops
`wget`, and removes the old system-owned keyboard user unit.

On a fresh installation before the first switch, use the flake's development
shell if `just` or flakes are not enabled yet:

```sh
cd ~/System
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just verify
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just preview
```

After reviewing the preview, switch **only when you choose to**:

```sh
NIX_CONFIG='experimental-features = nix-command flakes' nix develop . -c just switch
```

`build` writes a result link under `${XDG_STATE_HOME:-$HOME/.local/state}/nixos`,
outside the flake directory. `verify` does not switch generations. The existing
`activate.sh` and unqualified `nixos-rebuild` use the separate `/etc/nixos`
directory, **not** this flake; do not use them for this workflow.
