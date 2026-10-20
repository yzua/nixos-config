# Desktop peripheral controls

The desktop has these on-demand tools; the laptop profile is unchanged:

| Tool | Purpose |
| --- | --- |
| Piper | Logitech gaming-mouse DPI, buttons and supported onboard profiles |
| OpenRGB (USB lighting) | Device-isolated motherboard/cooler lighting |
| Cooler Status / `cooler-status` | Open a terminal showing cooler telemetry with liquidctl |

NixOS supplies the D-Bus-activated `ratbagd` mouse service. Two device-scoped
`hidraw` udev rules grant access to the active local session for the lighting
controller and cooler in `setup.peripherals`. They run before systemd's
`73-seat-late.rules`. There is no world-writable HID access, blanket input-group
membership, user SMBus permission, RGB server, globally configured I2C module,
or cooling initialization service. Approved lighting-only startup jobs are
separate from the interactive OpenRGB GUI.

Home Manager installs the apps. The OpenRGB menu entry calls `openrgb-usb`,
which creates a fresh device namespace with bubblewrap and exposes only the
configured controllers' HID nodes. Other HID, USB-bus, I2C, raw-memory and GPU
devices are hidden; a private process namespace prevents access through another
process's `/proc` entries. Software rendering draws the GUI without exposing GPU
devices. Only the separate `OpenRGB-usb` settings directory is writable in the
home directory. Normal active-session ACLs still apply; the wrapper never
requests elevated privileges and fails if the configured nodes are inaccessible.

Opening this launcher explicitly detects the permitted controllers. It does not
run at login, start an SDK server or connect to one. Detection can reset lighting;
closing OpenRGB may restore the cooler's hardware lighting behavior. The old
`--nodetect` entry was misleading: that flag also suppresses the GUI's Rescan
operation, so it is no longer used. Use the menu entry or `openrgb-usb`, not the
unrestricted `openrgb` command, for ordinary configuration. Do not run it as root.
Do not run OpenRGB and liquidctl writes against the same controller concurrently.
`cooler-status` uses only liquidctl's device-selected `status` operation, never
`initialize`, `set`, firmware updates, or non-volatile writes. Do not run
`liquidctl initialize` just to obtain readings: this can change pump/fan behavior.

## Verified devices and limitations

The inspected desktop has a G903 LS, Drop CSTM80, Gigabyte Z390 AORUS PRO-CF
with ITE `048d:8297`, Corsair H100i Platinum `1b1c:0c18`, RTX 2070, and a connected
LG ultrawide at 2560×1080 / 75 Hz. NVIDIA, Ethernet, storage and USB controller
drivers are bound; the keyboard and mouse are already working. Pointer
acceleration and key-repeat preferences were not changed. At the user's request,
static-white lighting commands were sent to the motherboard/header controller,
cooler and both active-profile mouse LEDs. Mouse DPI/mappings were compared before
and after and remained unchanged. No cooling, clock or firmware commands were sent.

- **Mouse:** pinned libratbag 0.18 includes original G903 and G903 HERO IDs;
  receiver ID alone does not distinguish them. Piper's actual detection still
  needs the active system service and an awake mouse.
- **Keyboard:** VIA has a definition for `359b:0004`, but the inspected keyboard
  exposes vendor HID collection `ff51:0058`, not VIA's `ff60:0061`. A matching
  USB ID is not proof of compatible firmware. No VIA shortcut, keyboard HID
  permission or firmware flashing was added. The vendor's documented RGB
  shortcuts work without a configuration app: Fn+W/S brightness, Fn+R/F hue,
  Fn+A animation, Fn+Z mono-colour. For static white, use Fn+Z then repeatedly
  tap Fn+G to reduce saturation to zero; Fn+T increases saturation. No firmware
  flash is needed for white. Do not hold Esc while plugging it in: that clears
  EEPROM and enters the bootloader.
- **Lighting:** pinned OpenRGB 1.0rc3 and liquidctl 1.16.0 match both USB RGB
  devices. OpenRGB's motherboard layout names do not exactly match the `-CF`
  DMI suffix, so a generic layout is possible. Case lights are controllable only
  if connected to a supported header/controller; software cannot establish the
  physical wiring. The cooler is configured for 16 pump LEDs plus eight LEDs
  across two stock RGB fans. OpenRGB's zero-sized default fan zone was corrected
  and the 24-LED total verified after relaunch. Replacement fan models may need a
  different count. A local `White` profile was saved for these USB controllers.
  The user confirmed the fans are white. A visual primary-colour test found that
  the pump responds to red, green and blue, but its all-white appearance still
  differs from the fans. A fresh enable produced five expected lighting writes
  without checksum warnings; the status reply reports firmware 1.1.15. This does
  not establish a hardware fault or a physical white-point match. An unverified
  pump-only colour-balance trial was reverted; all 24 LEDs were returned to
  standard `FFFFFF`. At the user's later request, the 16 pump/block LEDs were
  set to `000000` (off), leaving the eight fan LEDs at `FFFFFF`. Pump telemetry
  remained available and no cooling settings were written. The `usb-lighting`
  user service now reapplies header white, fan white and the block's configured
  white-balance correction at graphical login, waiting briefly for active-seat USB permissions. It shares
  a lock with `openrgb-usb` so they cannot write concurrently. OpenRGB profiles
  can replace those colours; close the GUI and run `restore-usb-lighting` to
  restore the requested settings. There is no continuous RGB daemon.
  After OpenRGB exits, its hardware-mode
  restoration can invalidate liquidctl's `leds_enabled` cache; clear only that
  lighting flag before reapplying colours, not cooling initialization.
  See the [white-tint investigation](research/corsair-h100i-platinum-white.md) for
  matching Corsair reports, relevant historical software bugs and limitations.
  Later calibration found a user-confirmed neutral-looking white at **8/8/255**
  (`0808FF`), though dim. Raising red/green to 12 and 16 made it warmer/yellowish,
  so the confirmed 8/8/255 balance is now in `setup.peripherals.cooler.pumpColor`
  and restored at login. Blue is already at maximum; software cannot increase it
  further to brighten the corrected white. This is colour compensation, not a
  verified hardware repair; no particular cause of the imbalance is proven.
- **GPU lighting:** the inspected MSI RTX 2070 has PCI IDs
  `10de:1f07 / 1462:3733`, missing from the pinned driver's registrations. After
  separate informed approval, an exact-ID derivative was built, its state read
  on only the verified NVIDIA port-1 adapter, and Direct `FFFFFF` applied at the
  existing 80% brightness without saving. Readback and the user's observation
  confirmed static white. This is experimentally validated on this card, not
  upstream-wide support. The dedicated `gpu-lighting` boot job uses the **same
  tested derivation**, exact four-ID/driver/port/node checks, signed read guards,
  isolated access, explicit brightness and state readback. It runs after the RAM
  job to avoid module-cleanup races in the normal boot transaction. Already-white
  state skips writes; errors are not blindly retried. No generic GPU GUI or bus
  permissions were added. A [support/experiment note](research/msi-rtx2070-rgb-support-draft.md)
  records the evidence and limitations.
- **RAM:** read-only, serial-filtered DMI inventory identifies four G.Skill
  Trident Z RGB DDR4 modules: two `F4-3000C16-8GTZR` and two
  `F4-3200C16-8GTZR`. These are separate from the USB lighting controllers.
  OpenRGB's `ENE SMBus DRAM` detector supports this controller family, but it
  remaps lighting-controller addresses during discovery. It is not read-only:
  targeted adapter access and discovery require a deliberate operation. After
  the initial one-time test, the user approved boot-time reapplication.
  The root-only `ram-lighting` oneshot verifies the configured PCI adapter,
  driver, name and character-device identity; it does not assume a bus number.
  It generates a complete detector registry using the pinned binary with no raw
  devices exposed, then enables only ENE DRAM and explicitly disables save mode.
  Inside the device-isolated process, only the selected adapter node is exposed.
  It requires the expected four ENE DRAM devices and sends Static `FFFFFF`.
  Discovery itself already remaps lighting addresses before this count check;
  applying white invokes discovery again. This is not a read-only probe or an
  address-level bus-permission filter. No SPD detector or save command is used.
  The helper grants no user ACL and unloads `i2c-dev` afterward if it loaded it
  and no other process needs it. Failure/timeouts also run module cleanup.
  No RAM/SMBus access is granted by the USB launcher. Do not enable generic DIMM
  or SPD detection, scan buses indiscriminately, or save controller firmware/NVM.
- **Displays:** Niri owns resolution, refresh, position and scale. A monitor
  that is disconnected cannot be live-validated. No extra display driver or
  forced resolution was added. Existing LACT supplies GPU controls.

## Activation and checks

Review `just home-preview` and `just preview`; apply Home Manager with
`just home-switch` and the system with `just switch`. The latter requires sudo
in the caller's terminal. Until the system switch, the new mouse service and
USB permissions are not active. Existing USB devices may retain their old
permissions even after switching. To reapply the rules without unplugging an
internal cooler/controller, run:

```sh
sudo udevadm trigger --subsystem-match=hidraw --action=change
sudo udevadm settle
```

This refreshes device permissions; it does not initialize cooling or set colours.
After activation, `ratbagctl list` checks mouse detection;
`cooler-status` requests telemetry without initializing cooling. After both
previews, `python3 -B tests/peripherals.py` checks generated rules and launcher
safety without probing hardware. `python3 -B tests/lighting-startup.py` tests
controller selection, lighting-only calls, LED ordering, fail-closed RAM registry
and adapter isolation with fake devices, including GPU skip/apply/readback and
signed ioctl errors.

After activation, inspect `systemctl --user status usb-lighting` and
`systemctl status ram-lighting gpu-lighting`. USB lighting restores at login;
RAM and GPU lighting restore at boot. Root service hardening and the actual four-controller
operation were tested in a transient validation unit. After the user activated
the reviewed configuration, the actual RAM, GPU and USB lighting services all
reported `active/exited`, `Result=success` and `ExecMainStatus=0`. The GPU binary
and scoped write path also passed the separate live experiment; its apply/readback
branches have hardware-free regression tests. Reboot/login persistence still
needs a real reboot to verify; suspend/resume restoration is not configured.
These jobs reapply volatile settings, not hardware firmware/NVM saves. The root
RAM/GPU helpers are not a concurrent public API: use the ordered systemd services,
not direct simultaneous invocations of their Python scripts.

## Primary compatibility sources

- [G903, libratbag 0.18](https://github.com/libratbag/libratbag/blob/v0.18/data/devices/logitech-g903.device),
  [G903 HERO](https://github.com/libratbag/libratbag/blob/v0.18/data/devices/logitech-g903-hero.device).
- [VIA CSTM80 definition](https://github.com/the-via/keyboards/blob/master/v3/drop/cstm80/cstm80.json),
  [VIA's firmware requirement](https://www.caniusevia.com/docs/configuring_qmk),
  [Drop configurator platforms](https://helpdesk.drop.com/hc/en-us/articles/44444057868305-How-to-Configure-your-Drop-Keyboard),
  [CSTM80 official shortcut guide](https://www3.corsair.com/Files/DROP/downloads/CSTM80%20WEB%20QSG%20-%20LANGUAGES%20SPLIT/CSTM80%20Web%20QSG%20R2-ENGLISH.pdf).
- [OpenRGB motherboard detection](https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/GigabyteRGBFusion2USBController/GigabyteRGBFusion2USBControllerDetect.cpp),
  [layout matching/initialization](https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/GigabyteRGBFusion2USBController/RGBController_GigabyteRGBFusion2USB.cpp),
  [cooler lighting](https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/CorsairHydroPlatinumController/RGBController_CorsairHydroPlatinum.cpp),
  [MSI GPU registrations](https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/MSIGPUController/MSIGPUController/MSIGPUControllerDetect.cpp),
  [ENE DRAM discovery/remapping](https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/ENESMBusController/ENESMBusControllerDetect.cpp),
  [ENE lighting and save controls](https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/ENESMBusController/RGBController_ENESMBus.cpp).
- [liquidctl cooler driver/safety](https://github.com/liquidctl/liquidctl/blob/v1.16.0/liquidctl/driver/hydro_platinum.py),
  [motherboard RGB driver](https://github.com/liquidctl/liquidctl/blob/v1.16.0/liquidctl/driver/rgb_fusion2.py).
