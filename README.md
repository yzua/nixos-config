# NixOS configuration

The `nixos` flake output imports the existing `configuration.nix`, which imports
this machine's `hardware-configuration.nix`. The lock file pins Nixpkgs. No old
machine configuration or Home Manager modules are imported.

Before the first switch, `just` and the flake CLI are not enabled in the running
system. Use the flake's development shell to run the non-activating commands:

```sh
cd ~/System
NIX_CONFIG='experimental-features = nix-command flakes' nix develop path:. -c just verify
NIX_CONFIG='experimental-features = nix-command flakes' nix develop path:. -c just preview
```

After reviewing the preview, switch **only when you choose to**:

```sh
NIX_CONFIG='experimental-features = nix-command flakes' nix develop path:. -c just switch
```

After that switch, `just` and the flake CLI are installed/enabled, so use
`just verify`, `just build`, `just preview`, and `just switch` directly.
`build` writes a result link under `${XDG_STATE_HOME:-$HOME/.local/state}/nixos`,
outside the flake directory. `verify` does not switch generations. The existing
`activate.sh` and unqualified `nixos-rebuild` use the separate `/etc/nixos`
directory, **not** this flake; do not use them for this workflow.
