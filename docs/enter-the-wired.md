# Enter The Wired on NixOS

The desktop gaming profile packages ACCELA and SLSsteam directly. It does not
execute Enter The Wired's shell installer, install Headcrab, downgrade Steam,
patch Steam's mutable launch scripts, or block Steam client updates. The laptop
profile does not import these gaming modules.

## Ownership and activation

- `packages/accela/` wraps the release AppImage, pinned by its extracted SHA-256.
  It contains the companion application and its bundled tools. Nix supplies the
  .NET 9 runtime on its private PATH, avoiding the application's automatic runtime
  installer. The installer repository's MIT license does not establish a license
  for the application bundle, so the package is classified as unfree.
- `packages/slssteam/` builds the pinned upstream i686 audit libraries with this
  repository's Nixpkgs. Like the upstream Nix package, this uses the static
  dependencies shipped in the SLSsteam source archive.
- `modules/nixos/gaming.nix` injects those libraries through the NixOS Steam
  wrapper's `LD_AUDIT`, using upstream's documented NixOS integration.
- `home-manager/modules/gaming.nix` installs ACCELA, registers `accela://`, and
  seeds writable settings only when absent. Existing configurations, including
  dangling symlinks, are never overwritten.

Review and apply Home Manager first, then NixOS, using the selected local outputs:

```sh
just check
just home-preview
just home-switch
just preview
just switch
```

If the checkout contains other pending changes, these commands include them too;
review the complete previews before switching. A build or preview alone does not
install the apps into the active profile.

After both switches, fully quit Steam and launch it normally again. Start the
companion from the ACCELA desktop entry or `accela`. No root application launch,
manual installer, or login autostart is required.

## Writable state and compatibility

Initial SLSsteam settings go to
`${XDG_CONFIG_HOME:-$HOME/.config}/SLSsteam/config.yaml`. New configurations enable
`SafeMode` and keep Lua plugins disabled. SafeMode checks the actual Steam client
library against upstream's online compatibility list, with a local cache. A
future Steam update can therefore disable SLSsteam instead of loading an
unrecognized client. This is not an account-safety or anti-cheat guarantee.

Initial ACCELA settings go to
`${XDG_CONFIG_HOME:-$HOME/.config}/Tachibana Labs/ACCELA.conf`, enabling its library
and SLSsteam modes. ACCELA may subsequently enable SLSsteam's local API and
update game-specific configuration; these files intentionally remain outside the
Nix store. Keep account credentials, tokens, and per-game keys out of this repo.
Application data and logs live under `${XDG_DATA_HOME:-$HOME/.local/share}/ACCELA`.

This setup does not install the alternative Psyche/Lua-plugin bundle or acquire
any game content. Client modification and ownership bypasses can violate Steam
terms and carry account and compatibility risks. Hash pinning verifies artifact
identity; it is not a malware audit.

To remove the setup, remove the ACCELA package/handler/config-seeding definitions
from the Home Manager gaming module and the SLSsteam override from the NixOS
gaming module, then preview and switch both profiles. Retain normal Steam and
other gaming settings. Writable application data is preserved; archive or remove
it separately only after closing both applications. Do not use the upstream
uninstaller, which assumes an imperative installation.

## Upstream references

- [Enter The Wired](https://github.com/ciscosweater/enter-the-wired)
- [SLSsteam release](https://github.com/AceSLS/SLSsteam/releases/tag/20261014151919)
- [SLSsteam NixOS installation](https://github.com/AceSLS/SLSsteam/wiki/Installation#nixos-added--written-by-developermikey)
- [SLSsteam configuration](https://github.com/AceSLS/SLSsteam/wiki/Configuration)
