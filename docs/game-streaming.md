# TV game streaming

Sunshine on the gaming host streams its existing Niri desktop to Moonlight clients.
The original **Desktop** entry leaves display modes unchanged. The separate
**TV Gaming (1440p)** entry selects the primary monitor's configured 16:9 TV mode
and opens Steam Big Picture. Games still run on the PC; the TV decodes the stream.

## Network and input policy

`setup.remoteDesktop` in `flake.nix` owns the streaming endpoints and TV mode.
The TV client address reuses `setup.pi.home.samsung.host`. Reserve these DHCP
leases in the router, or update the facts when addresses change.

Only the declared laptop and TV IPv4 addresses can access streaming ports, on
the declared host interface/address. Mandatory LAN/WAN encryption, authenticated
pairing, disabled UPnP, and local-only administration are preserved. The TV does
not get access to the administration port. Controller forwarding is enabled;
Sunshine presents an Xbox 360-compatible virtual gamepad for Steam/Proton games,
so games may show Xbox button labels even with a physical DualSense.

## TV application

The community [Moonlight Tizen client][client] supports Tizen 5.5 and newer.
Use its standard `Moonlight.wgt`, not the ForceGM variant intended for Tizen 9+.
Follow the upstream [installation guide][installation]. Installation requires
Developer Mode and is separate from normal paired remote control. Preserve
existing Samsung signing identities and unrelated TV application data; do not
use root access or debug-launch another application as an installation shortcut.

For this installation, upstream **v1.19.0** was downloaded and its GitHub release
SHA-256 digest verified before deployment:

```text
b5e64dbf0c79678400d82078d785a27073adf3cf08254843a97517312c0e184e  Moonlight.wgt
```

The TV reported installation completed, and a separate app-inventory read
confirmed `MoonLightS.MoonlightWasm`. No new SDK, container engine, or permanent
package was installed; the existing installer transport was used as a reference
for a bounded one-off deployment. The user activated the reviewed host preview, and the running Sunshine service
was verified to use mandatory encryption and enabled Xbox-compatible controller
forwarding. This is installation/configuration evidence, not yet a live
streaming/controller-performance test.

## Pair and play

1. Activate the reviewed host preview with `just switch` from this repository.
2. On the TV, open Moonlight and manually add the configured streaming host address.
   Automatic discovery is intentionally not published.
3. Select the host to obtain a PIN. On the PC, open `https://localhost:47990`,
   authenticate, and enter that PIN in Sunshine's pairing page. The existing admin
   login is in the caller's private Sunshine state directory, outside Git and the
   Nix store. Never paste it into chat or commit pairing keys.
4. Pair the DualSense with the TV: hold **Create + PS** until its light flashes,
   then select it in the TV's Bluetooth input-device list. Menu labels differ by
   firmware; look under External Device Manager / Input Device Manager. USB to
   the TV is an alternative. Standard buttons/sticks are the target; gyro and
   PS5-specific adaptive triggers are not promised.
5. Set Moonlight to **2560×1440, 60 FPS, SDR, stereo**, initially about **20 Mbps**.
   Use H.264 first; try HEVC after the basic test. Keep encryption mandatory. If
   networking or decoding stutters, reduce to 1080p/60 and retest.
6. Start **TV Gaming (1440p)**. The PC monitor temporarily changes mode as well;
   this is not an independent virtual TV display. Set each game's resolution to
   2560×1440 and a fullscreen/borderless mode so its image fills the 16:9 TV.
7. When finished, **quit the running application in Moonlight**, rather than only
   disconnecting, so Sunshine runs the undo command and restores the primary
   monitor's normal configured mode. Disconnect alone may leave the app/session
   resumable and its TV mode in place. Steam/games are not forcibly killed.

For manual display recovery, run the configured undo command from
`services.sunshine.applications.apps` on the gaming host, or use
`niri msg output '<primary-monitor-match>' mode '<normal-configured-mode>'`
with the primary monitor's values from `setup.monitors`.

The selected TV mode must be advertised in `niri msg outputs`; a different gaming
host should choose its own supported 16:9 mode. A 4K TV panel does not imply 4K
rendering, 120 FPS streaming, or HDR support throughout the Linux capture chain.
Ethernet on the PC and Ethernet or strong 5 GHz Wi-Fi on the TV are recommended.

## Native 4K/60 plan

The chosen next step is a **4K/60 display emulator (dummy plug)** on an unused
output of the discrete gaming GPU. No cable between PC and TV is required.
Check that the emulator explicitly advertises **3840×2160 at 60 Hz**; a “4K”
product that exposes only 30 Hz is insufficient. Select HDMI/DisplayPort according
to the GPU's available socket, not a motherboard video output.

The current TV entry remains the tested-policy **1440p fallback**, not a native
4K configuration. Once the emulator is available:

1. Inspect `niri msg outputs` and confirm its identity and advertised 4K60 mode.
2. Record those display facts in `setup`; do not guess connector names or timings.
3. Configure TV capture and game placement on that separate display while
   preserving the laptop entry's original physical-monitor capture.
4. Preview/review/activate the configuration, then test 4K60 picture, audio,
   controller input, and display cleanup on application quit.

The installed stock Niri cannot create an independent virtual output through its
normal IPC. The physical ultrawide advertises 4K only at about 30 Hz; forcing an
unsupported 4K60 mode is not the selected workaround. No compositor replacement,
boot/EDID override, or experimental gaming session was installed.

Although the selected TV has a 120 Hz panel, the Moonlight Tizen project describes
app rendering above 60 FPS as experimental. A 4K60 dummy plug does not establish
4K120 streaming, HDR support, or game-rendering performance at either resolution.

## Verification

`python3 -B tests/remote-desktop.py` evaluates host/client policy, including both
source-address firewall rules, mandatory encryption, controller mapping, and the
TV mode/restore commands. Run `just check` and `just preview` before activation.
TV pairing and the original Desktop stream were confirmed live. The initial TV
Gaming launch failed with `-1`: Sunshine's Boost.Process parser does not accept
POSIX single-quoted monitor names. The mode commands now use bare executable
wrapper paths, with shell quoting inside those wrappers. Regression checks
inspect the generated wrapper derivations without building or activating.

Both mode-change and restore wrappers were also replayed under Sunshine's actual
session environment through Boost.Process v1; the live output changed to
2560×1440 at about 60 Hz and was restored successfully. Full TV Gaming launch,
full-screen picture, sound, controller input, and restoration after quitting
still need to be checked on the TV after the corrected preview is activated.

[client]: https://github.com/brightcraft/moonlight-tizen
[installation]: https://github.com/brightcraft/moonlight-tizen/wiki/Installation-Guide
