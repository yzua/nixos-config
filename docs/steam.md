# Steam and custom Proton runners

The desktop gaming module registers two optional Steam compatibility tools:

- **GE-Proton**, from the pinned Nixpkgs `proton-ge-bin` package.
- **Proton-CachyOS**, from a checksum-pinned official prebuilt **Steam Linux
  Runtime (`slr`), baseline `x86_64`** release. The package definition is in
  `packages/proton-cachyos-bin/default.nix`; no third-party cache or local Wine
  compilation is needed.

Valve's default Proton and existing per-game compatibility selections are not
changed. These tools are scoped to Steam; Lutris is unchanged. The laptop profile
has no Steam gaming module.

## Apply and select

From the repository root, review and apply the system configuration:

```sh
just check
just preview
just switch
```

Fully exit and restart Steam after switching. For an individual game, open
**Properties → Compatibility**, enable **Force the use of a specific Steam Play
compatibility tool**, and select **GE-Proton** or **Proton-CachyOS**.

Keep Valve's Proton as the normal default and try a custom runner when a game
needs it. Custom runners are not guaranteed to improve performance. Consult
[ProtonDB](https://www.protondb.com/) for game-specific reports; avoid experimental
DLL injection or layers in anti-cheat games unless explicitly supported.

## Existing performance tools

GameMode and MangoHud are already enabled, but are opt-in per game. To use both,
set this in the game's **Properties → General → Launch Options**:

```text
gamemoderun mangohud %command%
```

Remove the launch option to stop requesting them. No global overlay, native
Wayland override, extra Vulkan layer, or kernel tuning is enabled here.

## Updating Proton-CachyOS

Use an official [Proton-CachyOS release](https://github.com/CachyOS/proton-cachyos/releases)
with an `slr-x86_64.tar.xz` asset, not an Arch-native build or an `x86_64_v3`
build. Update the package's version and SHA-256 together, verifying the intended
asset against its official release metadata. Preserve the bundled licenses and
Steam Linux Runtime layout. The package generates Steam discovery metadata using
upstream's relative install-path convention and checks required files at build
time. Run the checks and system preview again before switching. Changing runners
can update a game's Wine prefix, so back up important saves before experimenting.
