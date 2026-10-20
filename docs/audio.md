# Headset playback tuning

The desktop's Home Manager profile starts EasyEffects in the background at login.
It keeps the physical device as the system default and does not automatically
process microphone streams or enable microphone monitoring. The existing PipeWire
RNNoise microphone filter is separate and unchanged.

The `headset-gentle` preset loads only for the device and **active route description**
in `flake.nix`'s `setup.audio`. Other outputs load `unprocessed`, an empty effects
chain. This prevents headset EQ from following a switch to speakers or HDMI.
The laptop profile does not enable EasyEffects.

EasyEffects starts after the PipeWire/WirePlumber user services and waits up to
20 seconds for the default **physical** output and its playback ports. On timeout
it exits before intercepting application audio; systemd retries startup. This is
a mitigation for early-login initialization stalls, not a guarantee against all
EasyEffects failures. Noctalia uses the same readiness check at login to avoid
missing the default output; it still starts after the timeout if no audio device
is connected.

The starting EQ adds 2 dB below roughly 100 Hz, cuts 1.5 dB around 300 Hz, and adds
1 dB around 3 kHz, with a −4 dB preamp for headroom. This is a mild preference
preset, **not** a measured headphone correction or an emulation of Windows.
It may sound quieter; do not judge quality solely by loudness.

## Controls

Open **Easy Effects** from the application launcher. Use its global bypass switch
to compare with the original sound. The equivalent terminal toggle is:

```sh
easyeffects --bypass-toggle
```

Closing the window leaves background processing running. To stop it for the
current session:

```sh
systemctl --user stop easyeffects.service
```

The service starts again at the next graphical login. To resume immediately:

```sh
systemctl --user start easyeffects.service
```

Home Manager owns the login service; leave the application's separate login
autostart setting off. Save experiments under a **new preset name**, because
`headset-gentle`, `unprocessed`, and the device autoload mapping are managed files.
The application's other settings remain writable; service startup reapplies only
playback routing, microphone-monitoring safety, and flat-fallback preferences.

Apply changes through `just check`, `just home-preview`, review, then
`just home-switch`. No NixOS rebuild or firmware update is needed. After a preview,
`python3 -B tests/easyeffects.py` checks generated presets, autoload filenames,
headroom, startup settings, and microphone safety without touching live audio.
`python3 -B tests/audio-startup.py` tests the readiness gate offline, including
incomplete device enumeration, alternate outputs, and timeouts.

## Troubleshooting silence after login

If volume buttons do nothing, compare the shell and PipeWire views:

```sh
noctalia msg volume-up 1
wpctl status
wpctl get-volume @DEFAULT_AUDIO_SINK@
pw-link -l
```

If Noctalia reports `no default output` but `wpctl status` shows a physical default,
its audio view may have failed to initialize. Restart the desktop bar (or log out
and back in); increasing the hardware volume does not repair that view.

An active `easyeffects.service` alone does **not** prove playback works. When apps
are routed to `easyeffects_sink`, there must also be a linked processing path from
that sink through the `ee_soe_*` nodes to the selected physical output. If that
path is missing, stop EasyEffects using the command above to restore direct
routing. Restart it only after the physical output is available.

After applying a startup change, verify a fresh login: play audio, test the
normal volume buttons, check the physical default, and inspect the complete
EasyEffects link path. Generated-config and offline tests cannot replace that
cold-login check.
