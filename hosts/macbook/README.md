# MacBookPro12,1 notes

This host targets the Early-2015 13-inch Intel MacBook Pro: Broadwell integrated
graphics, a dual-core/four-thread CPU, and 8 GB shared RAM. Hardware/storage facts
remain in the unmodified generated `hardware-configuration.nix`. Its hostname and
system output are `laptop`; its standalone home output is `yz@laptop`.

## Hardware choices

The maintained [exact-model nixos-hardware profile][model] and its [Apple base][apple]
were consulted without introducing another flake input or changing dependency pins.
The laptop uses:

- Kernel `i915`/Mesa graphics, early graphics initialization, and the legacy
  [Intel i965 VA-API driver][vaapi] for supported hardware video codecs.
  This is separate from Vulkan speech inference; it adds no OpenCL runtime.
- NixOS's [FaceTime HD module][camera], which provides the kernel-matched driver,
  fixed-hash Apple firmware, and camera suspend/resume hooks. Experimental sensor
  calibration remains disabled. Driver installation is not a camera-call test.
- `mbpfan`, UPower, power-profiles-daemon, touchpad settings, and SSD TRIM.
  The [common laptop policy][laptop] avoids TLP when power-profiles-daemon is enabled;
  this host likewise uses one power-management owner, not competing daemons.
- The generated Broadcom firmware import and Intel microcode settings.
  No T2/Touch Bar/Apple-SPI, discrete-GPU, or `xe` fixes apply to this model.

Upstream documents Broadcom suspend/resume and immediate USB wake workarounds.
They are not applied speculatively: first test repeated lid suspend/resume on AC
and battery, including Wi-Fi reconnect and an external USB device. Adopt a scoped
fix only if the corresponding symptom occurs. Do not copy the old governor
comment as a claim that modern Intel `powersave` always fixes the CPU at 800 MHz.

## Lab and voice

The standalone home profile includes `pi-re`, its pinned Android/static-analysis
engines, and the large multilingual `large-v3-turbo` voice model with Arabic/English
selection. The emulator is on-demand, not a login service. Its host-specific
starting limits are two cores, 2048 MiB RAM, and a 300-second boot deadline; the
SDK is composed from the same selected host settings.

The owned emulator cold-booted and rooted in 57 seconds, passed a second root
check, and stopped cleanly. A synthetic one-second-silence transcription completed
on Intel Vulkan in about 22 seconds; real microphone/Arabic transcription and
thermal behavior still need runtime checks. Large transcription, an emulator, Ghidra,
and browser tabs compete for the same RAM. Do not run all of them concurrently
and mistake swap availability for adequate working memory.

## VPN identities and secrets

Mullvad, NetBird, and Tailscale are configured, but installation and enrollment
are separate. Each receives its own device identity; never copy another machine's
`/var/lib/netbird`, `/var/lib/tailscale`, or Mullvad device state. Account/SSO
approval and server-side network policy remain external to Nix.

The existing system SOPS identity is provisioned privately outside Git/the Nix
store, as explicitly requested. The scoped NetBird/Mullvad firewall and private
DNS modules require successful decryption before NetBird can start. Tailscale
keeps DNS, subnet-route acceptance, exit nodes, and Tailscale SSH disabled; the
account may operate its own client. Ordinary remote access uses key-only OpenSSH.

Enable Mullvad LAN sharing before connecting over LAN SSH. Verify the three
clients together: LAN access does not guarantee arbitrary mesh traffic bypasses
Mullvad. The private bypass grants only its declared DNS/HTTPS destinations,
not a global mesh exemption. Leave a local console available during first connect.

## Desktop and laptop shortcuts

Retina output stays at 2×. Laptop-only font sizes are desktop/popups 11,
applications 12, and terminal 13. VS Code uses normal UI zoom and 13-point editor
and integrated-terminal text; the desktop keeps its existing larger settings.
Firefox, Ghostty, VS Code, Telegram, Vesktop, Mullvad, NetBird, and Noctalia start
with Niri. Full app startup trades more RAM for convenience; the emulator still
does not start automatically. A hot config reload does not rerun startup commands.

On the MacBook, **Mod** is the Command/Super key. Shared desktop navigation,
workspace, volume, display-brightness, and media shortcuts remain available.
Laptop additions avoid keys absent from the built-in keyboard:

| Shortcut | Action |
| --- | --- |
| Mod + Return | Terminal |
| Mod + Space | App launcher |
| Mod + Shift + S | Region screenshot |
| Mod + Ctrl + Shift + S | Whole-screen screenshot |
| Mod + Shift + Backspace | Lock |
| Keyboard-backlight keys | Raise/lower/toggle keyboard illumination |
| Mod + D | Toggle dictation |
| Mod + X | Voice action |
| Mod + Shift + Escape | Cancel voice action |

Mac function/media-key mode affects whether the physical key needs Fn. Test
actual key events before adding `hid_apple` function-mode overrides.

## PC desktop client

Open **PC Desktop** from the launcher to view/control the PC's existing desktop.
Moonlight pairing and encrypted LAN streaming were tested at 2560×1080/60 FPS,
with NVIDIA NVENC on the host and Intel i965 hardware decoding on this laptop.
The observed overlay showed 0% network frame drops, about 1 ms network latency,
and 0.26 ms average decoding time; these are LAN test observations, not a Wi-Fi
performance guarantee. Reconnection passed, and the user confirmed physical
keyboard/mouse control. The ultrawide display is letterboxed; host display modes
were not changed. Monitor-off, locking, and suspend/resume streaming remain
separate tests.

Streaming is restricted to the configured laptop and TV LAN addresses and requires
mandatory encryption and authenticated pairing. The laptop's **Desktop** entry
still leaves host display modes unchanged; the separate [TV Gaming entry](../../docs/game-streaming.md)
temporarily selects a 16:9 mode. UPnP and Sunshine service
publishing are disabled; the administration interface permits only local access.
Open `https://localhost:47990` on the host to revoke a paired client. The generated
admin login is private at `~/.local/state/sunshine/private/admin.json` on the host;
it and the pairing keys remain outside Git and the Nix store. Reserve the LAN
addresses in the router, or update `setup.remoteDesktop` if DHCP changes them.
The host's Sunshine service starts with its graphical session; log in there,
then open **PC Desktop** on the laptop. Use **Ctrl + Alt + Shift + Q** to disconnect
without closing the PC's apps. Host monitor modes are not changed by this entry.

## Remaining checks and decisions

- **Backups:** choose encrypted off-device backups and test a restore. Agent
  history, Git, and local Nix generations are not complete home/data backups.
- **Disk encryption:** root and disk swap remain unencrypted by explicit user
  choice. Shared SSH/API/decryption keys increase the impact of losing this
  laptop; private file permissions do not protect against offline disk access.
- Test camera capture, speakers, headphones, microphone, Bluetooth reconnect,
  brightness/media keys, keyboard backlight, touchpad, lid lock/suspend, and
  external display behavior. Repeat camera and network checks after resume.
- Check battery health/runtime and fan response under emulator/voice load.
- Browser sync/sign-in, password database access, passkeys, and account sessions
  are not supplied by declarative Firefox profiles or this credential migration.
- Printing, YubiKey PC/SC tools, and an Apple firmware update/recovery path are
  separate needs; do not assume fwupd alone updates this Mac's firmware.
- OpenCode 2 credentials were imported, but its empty provider/model catalog
  was reproduced on both machines before these additions. It remains a separate
  pre-existing application issue, not a verified working AI route.

[model]: https://github.com/NixOS/nixos-hardware/blob/60a624466c08787ee8303393b7d4752d1826f14f/apple/macbook-pro/12-1/default.nix
[apple]: https://github.com/NixOS/nixos-hardware/blob/60a624466c08787ee8303393b7d4752d1826f14f/apple/default.nix
[laptop]: https://github.com/NixOS/nixos-hardware/blob/60a624466c08787ee8303393b7d4752d1826f14f/common/pc/laptop/default.nix
[camera]: https://github.com/NixOS/nixpkgs/blob/6fcc160353f63555b560f25588925133c8f61f2a/nixos/modules/hardware/video/webcam/facetimehd.nix
[vaapi]: https://github.com/NixOS/nixpkgs/blob/6fcc160353f63555b560f25588925133c8f61f2a/pkgs/by-name/in/intel-vaapi-driver/package.nix
