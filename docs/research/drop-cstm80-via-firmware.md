# Drop CSTM80: VIA firmware on Linux

Research date: **2026-10-21**. Initially research-only; subsequently updated with
separately authorized bootloader inspection and a one-time VIA application flash.
See the actual results below; no bootloader update or automatic retry occurred.

## Conclusion

**Yes: an official VIA-project CSTM80 UF2 exists, and Linux can install UF2
through the keyboard's bootloader drive.** Compiling custom firmware or using
Windows is not inherently required. This is a much stronger finding than merely
finding a VIA JSON definition. However, the running keyboard's PCB revision and
bootloader were initially unverified; the later inspection below confirms the
CSTM80 bootloader. **Restoration of the exact installed firmware/settings remains
unverified**, although a genuine vendor-distributed stock XAP image has now been
extracted and validated offline. The next stage is separately authorized flashing after reviewing the remaining
recovery limitations, **not automatic installation**. That authorization and
application flash subsequently occurred; VIA enumeration and normal typing
were confirmed. Browser configuration communication was subsequently confirmed;
final lighting appearance/persistence remains unverified. [VIA downloads][downloads] [QMK tinyuf2][flashing]

For static white alone, flashing remains optional: Drop documents **Fn+Z** mono
mode, **Fn+G** saturation down, and **Fn+W/S** brightness. White requires reducing
saturation, not cycling hue. VIA is useful for graphical remapping and lighting
configuration, not necessary just to obtain white. [Drop guide][guide]

## Supported: identity, firmware and source

### Running device versus intended replacement

The parent investigation read descriptors only and observed:

- manufacturer `Drop Inc.`, product `CSTM80`, USB **359b:0004**;
- `bcdDevice = 0100`;
- vendor HID collections **ff51:0058**, **ff51:0062**, **ff51:0063**;
- **no ff60:0061** collection.

These are local observations, not proof of a particular PCB revision. In
particular, `bcdDevice` is a USB device-release field, **not necessarily an actual
firmware version**: QMK's board metadata sets `device_version: 1.0.0` and its USB
descriptor emits the configured `DEVICE_VER`. [Board metadata][board]
[USB descriptor][usbdescriptor]

The existing **ff51:0058 positively matches QMK XAP's declared interface**;
QMK's own client defines `XAP_USAGE_PAGE = 0xFF51` and `XAP_USAGE = 0x0058`.
That identifies the intended XAP interface, but does not establish the installed
build's exact version, supported commands, compatibility with a particular Drop
or upstream XAP client, or export/migration capability. [XAP client][xap]

VIA uses a different interface. QMK Raw HID defaults to **ff60:0061**, and the
current VIA web app explicitly filters for that collection. The CSTM80 VIA
keymap enables `VIA_ENABLE = yes`; QMK consequently enables Raw HID and dynamic
keymaps. Thus matching VID/PID or loading JSON alone cannot convert this running
XAP firmware into VIA. After replacement, the intended firmware should expose
VIA Raw HID and answer its protocol requests. [Raw HID][rawhid]
[VIA app filter][viafilter] [Build feature selection][features]

### Exact official prebuilt found

The live **VIA Firmware Downloads** page lists **`drop_cstm80_via.uf2`**, linking
to `the-via/firmware`. Use that official index, not similarly named third-party
files. The artifact is VIA-project-distributed; no Drop signature or
vendor-certified revision matrix was established. [Downloads][downloads]
[Artifact][artifact]

The parent downloaded the pinned artifact to temporary storage and inspected it
offline; no bytes were sent to hardware:

| Field | Inspected value |
| --- | --- |
| Repository pin | `bc32102518533741af10b05ebbad38c4eef34997` |
| File | `drop_cstm80_via.uf2` |
| SHA-256 | `1f89f71e4e0b1c27fb6991e1c648dc051494b2a892c0ae2cef84884daa5d4b8a` |
| File size | 95,232 bytes; 186 UF2 blocks |
| Application payload | 47,616 bytes |
| Target range | `0x08004000` to `0x0800fa00` exclusive |
| UF2 family | `0x6b846188` |
| Flags | `0xa000`: family ID and extension tags present |
| Device-type tag | `0xc8a729`, value `0x8bfa7750` |

The device-type value matches the CSTM80's QMK `UF2_DEVICE_TYPE_ID`, and the
application start matches QMK's STM32F303 tinyuf2 linker reservation of the first
16 KiB. These checks validate file structure and declared target, **not physical
PCB/bootloader compatibility**. [Board rules][rules] [Linker layout][linker]
[UF2 specification][uf2]

The artifact's last-changing commit is
[`09d036c3f74c187f8ea215838a4655a808967f35`][artifactchange], a 2026-08-12 sync.
The distribution README describes periodic QMK builds; the current VIA userspace
workflow points at moving **QMK `develop`**, not a pinned release. Therefore the
artifact pin/hash does **not** identify a reproducible exact QMK/userspace source
pair. Do not claim the inspected binary was built from the source pins below.
[Distribution policy][firmwarereadme] [Build workflow][workflow]

### Maintained public implementation

At QMK `180f394b489c238cb231c2bf8b080262155e03c0`, `drop/cstm80` specifies:
**STM32F303**, **tinyuf2** (not ordinary STM32 DFU), I2C external EEPROM,
IS31FL3733 RGB Matrix, `359b:0004`, and ANSI TKL/F13 layout. Only one CSTM80 target
is present, without revision subtargets; that is not proof that every unit ever
sold has identical hardware. The maintainer is `zvecr`. [Board][board]
[Board README][boardreadme]

Mainline QMK has the **default** keymap; VIA keymaps have moved to the official
external userspace. At VIA userspace
`3e440ab72335c56041689a173ea53a512660b104`, the exact CSTM80 VIA keymap exists,
enables VIA, and sets **eight dynamic layers**. VIA's definition at
`9e3e9f4aa9f50f9439fdebc747560f51aaf109a0` matches the USB IDs and 6x17 matrix,
and exposes standard QMK RGB Matrix controls. [VIA keymap][viakeymap]
[VIA definition][definition] [Current integration model][configuring]

**Mappings/settings can change:** the published VIA keymap uses **Fn+Backspace
for `QK_BOOT`** and **Fn+Space for `EE_CLR`**. Do not assume the installed Drop
shortcut set, XAP profiles, macros or saved lighting migrate. VIA initializes
its own dynamic map storage, and EEPROM clearing loses saved settings.
[VIA keymap][viakeymap] [VIA initialization][configuring] [Bootmagic][bootmagic]

## Could build: Linux source path, not needed for the prebuilt

The documented source route is a QMK checkout with submodules, the official VIA
userspace overlay, QMK CLI/Python dependencies, make and the ARM cross-toolchain.
After selecting that overlay, **`qmk compile -kb drop/cstm80 -km via`** is the
build-only target. Merely cloning current QMK and requesting `via` is insufficient
because the keymap is external now. Alternatively, enabling `VIA_ENABLE = yes`
in a local keymap is technically supported, but retaining the published keymap's
layer count and the official definition is preferable to inventing a variant.
No compilation or dependency installation was tested here. [Userspace setup][overlay]
[CLI][cli] [Build environment][environment] [VIA integration][configuring]

For an already-built correct UF2, QMK's **tinyuf2** documentation permits copying
the file to the newly enumerated bootloader disk from Linux; QMK Toolbox is not
required. QMK CLI also documents a compile-and-flash route. **Both copying UF2
to that disk and `qmk flash` are firmware writes**, not inspection steps. Do not
substitute generic `dfu-util` commands at flash address `0x08000000` or write a
bootloader/production image. [Tinyuf2 workflow][flashing] [CLI][cli]

VIA configuration subsequently requires a WebHID-capable browser, user
permission to the intended HID interface and successful protocol identification;
USB permission changes cannot add the missing interface to the old firmware.
The web app communicates with compatible firmware and saves configuration to
nonvolatile memory, so opening/configuring it is not a descriptor-only operation.
[VIA filter][viafilter] [VIA protocol/configuration][configuring]

## Stock recovery image found; exact rollback remains untested

Drop's current support article documents **Drop Keyboard Configurator → Flash
Firmware**, but offers its app for **Windows/macOS only**. It does not supply a
verified Linux CSTM80 stock export/restore procedure. Its separate downloadable
stock examples cover CTRL, ALT, SHIFT and Carina, **not CSTM80**. A current QMK
`default` build would be a different firmware, not restoration of the installed
Drop/XAP image. A later offline examination of the official Configurator resolved
the missing stock-image lead as described below; no successful rollback has
been tested. [Drop configuration article][dropconfig] [Stock examples][dropstock]

The model README documents **double-tapping the reset button under the spacebar**
as a bootloader route; **holding Esc during connection invokes Bootmagic and
clears EEPROM**. These are recovery *entry methods*, not rollback. Neither was
performed during the initial research; the later authorized physical-reset
inspection is recorded below. [Board README][boardreadme] [Bootmagic][bootmagic]

UF2 bootloaders *may* expose `INFO_UF2.TXT` and `CURRENT.UF2`. Current upstream
TinyUF2 source generates `CURRENT.UF2` by reading application flash, but that
upstream implementation is **not proof of the installed Drop bootloader**.
If present, readback must be validated for completeness, addresses, tags and
restorability before calling it a rollback image. It also does not automatically
back up the board's **external I2C EEPROM** or prove restoration of XAP profiles.
Do not promise that all UF2 implementations expose a usable backup.
[UF2 optional files][uf2] [TinyUF2 readback implementation][tinyreadback]
[External EEPROM][board]

## Actual bootloader inspection: completed, backup unusable

The user subsequently authorized inspection and used the physical double-tap
reset route. This is their only keyboard; no spare is available. After fixing a
helper readiness race (wait for UDisks filesystem registration, not merely the
kernel block node), the verified keyboard disk was mounted read-only and its
identification and `CURRENT.UF2` files copied to private user state outside Git.

Observed identification:

- boot USB **359b:0003**;
- **TinyUF2 Bootloader drop-1.0.1**;
- model **Drop Inc. CSTM80**, board ID **CSTM80**;
- build date **Jul 13 2023**.

**`CURRENT.UF2` is 262,144 bytes of zeros.** Two matching file reads and the
recorded SHA-256 agree, but there are no valid UF2 blocks or application bytes.
This is **not a usable firmware backup** and cannot establish rollback. A
likely explanation was found in the public Drop-targeted TinyUF2 fork: its
readback code compares an absolute application address (`0x08004000` or higher)
against a relative flash size (`128 * 1024`), so it leaves every returned buffer
zero-filled. Its advertised readback length is exactly 262,144 bytes. This
predicts the observed result without implying erased firmware. However, that
public fork exposes `drop-1.0.0`, not the installed `drop-1.0.1`, so exact build
equivalence is unproven. The matching TinyUSB/HAL dependency revisions strengthen
but do not prove the explanation. **Do not replace the bootloader to fix
readback.** Do not truncate, repair, or flash the zero file. [Drop readback source][dropreadback]
[Drop flash-size source][dropflashsize] The wizard's completion message meant inspection finished, not that
backup validation passed; its structured report explicitly rejects this file.

The user reconnected normally and ordinary keyboard mode returned. **No firmware
was flashed, no bootloader was replaced, and no EEPROM-clear command was sent.**
A separately reviewed stock/recovery path or explicit acceptance of the unresolved
rollback risk remains necessary before any firmware replacement.

## Vendor-distributed stock XAP image: extracted and checked offline

The [official Drop article][dropconfig] links its Windows Configurator download.
That installer identifies the update bucket used by Drop; the public
[update manifest][dropmanifest] identifies version **25.5.19-1291**. The
[versioned installer][dropinstaller] was downloaded to temporary storage and
extracted **without executing the installer or any extracted program**. Its
125,196,132-byte size and SHA-512 matched the manifest; SHA-256 is
`8c3bd7acf9be8bb44cd25acb2a67399b1061860902bd957c79f3ec7a0f1ab056`.

The image at `resources/extraResources/firmware/drop_cstm80_stock.uf2` has:

| Property | Verified value |
| --- | --- |
| Size | 104,448 bytes; 204 UF2 blocks |
| SHA-256 | `8e13b8885b96cad317700ce54522b9f12abe5a8ecc3527b9c44ea30b0dec8d6b` |
| Application range | `0x08004000–0x08010c00` exclusive |
| Family / device type | `0x6b846188` / `0x8bfa7750` |
| Embedded board metadata | `drop/cstm80`, STM32F303, tinyuf2, USB `359b:0004`, XAP enabled |
| HID interface | `ff51:0058` present; VIA `ff60:0061` absent |

The Configurator's UI calls this **QMK XAP (stock)** and explicitly describes it
as **Original firmware that the CSTM80 shipped with**. Static application code
maps `cstm80_stock_xap` to the above file and recognizes CSTM80 bootloader PIDs
`0003` and `0011`, including the inspected keyboard's `359b:0003`. Both downloaded
official installer versions contain the byte-identical stock image.

The parent independently verified the stock and VIA images' hashes, UF2
headers/counts, contiguous application-only addresses, family/device tags,
plausible application vectors and distinct XAP/VIA descriptor signatures. Both
are preserved privately under
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/keyboard-via/firmware/`, with provenance
and hash reports; firmware binaries are not added to Git.

This is a **vendor-distributed stock application recovery candidate**, not a
readback of this particular unit, proof of an identical installed version,
backup of EEPROM/profiles/bootloader, or demonstrated successful restore.
It materially improves recovery preparedness without eliminating flash risk.
The zero-filled `CURRENT.UF2` must never be used as a restore image.

## Authorized VIA application flash: performed

After reviewing the verified stock image and the remaining risks, the user
explicitly selected flashing VIA now without a spare keyboard. The guarded
one-time helper revalidated both image hashes/UF2 targets, the physical USB
port, exact bootloader IDs/information and block/mount major-minor identity.
It inspected read-only first, then deliberately mounted only that boot volume
writable and sent the verified VIA application image. A durable local marker
prevents rerunning the same write session. No bootloader image, explicit
EEPROM-clear command or automatic recovery/retry write was sent.

The write returned **`EIO` (Input/output error)** before transport completion
could be confirmed. The helper did **not** retry: the same keyboard subsequently
reappeared as `359b:0004` with VIA **`ff60:0061`**, independently confirmed from
sysfs. The user then confirmed normal typing, including the requested ordinary
key checks. These observations establish running VIA-interface firmware and
usable typing, not a byte-for-byte readback of the flashed image; the earlier
readback bug prevents that verification. The disconnect during application
handover is consistent with the transport error but is not proven as its cause.

The configuration now declares an active-seat uaccess rule restricted to the
verified VIA interface number `01`. It uses the vendor/product/interface
properties imported by systemd's `60-persistent-input.rules`, avoiding ATTRS
from different USB parents. Other keyboard HID interfaces stay ungranted.
After activation/reconnect, live permission checks confirmed user read/write
access to the VIA HID node only, not the other two keyboard HID nodes. The user
authorized the CSTM80 in VIA and displayed its keyboard configuration. Two
accidentally remapped G/H keys were restored through VIA, and the user confirmed
completion, providing an actual configuration-communication check. Final white
lighting appearance and reconnect persistence were not independently verified.
Firmware remains on the keyboard; NixOS never automatically reflashes it at boot.
Private recovery images remain outside Git.

## Preparation / authorization checklist

Proceed with **preparation for VIA**, not an unconditional claim of safe flashing:

1. Preserve the pinned official UF2 and its hash/target inspection; record the
   current mappings and lighting separately.
2. Seek **separate approval for entering the bootloader**. Prefer the documented
   physical reset route over EEPROM-clearing Bootmagic when preserving settings
   matters. Identify the actual bootloader/board from its information, with no
   UF2 copy to the device.
3. Assess `CURRENT.UF2` readback if exposed; obtain vendor stock firmware or
   support confirmation where readback/restore is inadequate. Explicitly accept
   any unresolved stock/settings rollback limitation before replacing firmware.
4. Only with board/bootloader matching, stable power, a spare keyboard and further
   explicit authorization should installation and post-flash VIA/key/lighting
   verification occur. Do not touch the bootloader itself.

**Bottom line:** official VIA firmware makes this a plausible, Linux-native
upgrade path. The remaining gate is physical target/recovery verification—not
absence of a VIA build, nor a need for Windows.

[guide]: https://www3.corsair.com/Files/DROP/downloads/CSTM80%20WEB%20QSG%20-%20LANGUAGES%20SPLIT/CSTM80%20Web%20QSG%20R2-ENGLISH.pdf
[downloads]: https://www.caniusevia.com/docs/download_firmware/
[artifact]: https://github.com/the-via/firmware/blob/bc32102518533741af10b05ebbad38c4eef34997/drop_cstm80_via.uf2
[artifactchange]: https://github.com/the-via/firmware/commit/09d036c3f74c187f8ea215838a4655a808967f35
[firmwarereadme]: https://github.com/the-via/firmware/blob/bc32102518533741af10b05ebbad38c4eef34997/README.md
[workflow]: https://github.com/the-via/qmk_userspace_via/blob/3e440ab72335c56041689a173ea53a512660b104/.github/workflows/build_binaries.yaml
[board]: https://github.com/qmk/qmk_firmware/blob/180f394b489c238cb231c2bf8b080262155e03c0/keyboards/drop/cstm80/keyboard.json
[boardreadme]: https://github.com/qmk/qmk_firmware/blob/180f394b489c238cb231c2bf8b080262155e03c0/keyboards/drop/cstm80/readme.md
[rules]: https://github.com/qmk/qmk_firmware/blob/180f394b489c238cb231c2bf8b080262155e03c0/keyboards/drop/cstm80/rules.mk
[linker]: https://github.com/qmk/qmk_firmware/blob/180f394b489c238cb231c2bf8b080262155e03c0/platforms/chibios/boards/common/ld/STM32F303xC_tinyuf2.ld
[usbdescriptor]: https://github.com/qmk/qmk_firmware/blob/180f394b489c238cb231c2bf8b080262155e03c0/tmk_core/protocol/usb_descriptor.c
[xap]: https://github.com/qmk/qmk_xap/blob/601efdb4abd0ebcc7e2082e2913f5373693da89c/src-tauri/src/xap/client.rs
[rawhid]: https://docs.qmk.fm/features/rawhid
[viafilter]: https://github.com/the-via/app/blob/935106a990af39bdd1ade881c02366eac486240d/src/shims/node-hid.ts
[features]: https://github.com/qmk/qmk_firmware/blob/180f394b489c238cb231c2bf8b080262155e03c0/builddefs/common_features.mk
[viakeymap]: https://github.com/the-via/qmk_userspace_via/tree/3e440ab72335c56041689a173ea53a512660b104/keyboards/drop/cstm80/keymaps/via
[definition]: https://github.com/the-via/keyboards/blob/9e3e9f4aa9f50f9439fdebc747560f51aaf109a0/v3/drop/cstm80/cstm80.json
[configuring]: https://www.caniusevia.com/docs/configuring_qmk
[overlay]: https://docs.qmk.fm/newbs_external_userspace
[cli]: https://docs.qmk.fm/cli_commands
[environment]: https://docs.qmk.fm/newbs_getting_started
[flashing]: https://docs.qmk.fm/flashing#tinyuf2
[bootmagic]: https://docs.qmk.fm/features/bootmagic
[dropconfig]: https://helpdesk.drop.com/hc/en-us/articles/44444057868305-How-to-Configure-your-Drop-Keyboard
[dropstock]: https://helpdesk.drop.com/hc/en-us/articles/37937816517393-Mechanical-Keyboards-Quick-Solutions-for-Common-Problems
[uf2]: https://github.com/microsoft/uf2#files-exposed-by-bootloaders
[tinyreadback]: https://github.com/adafruit/tinyuf2/blob/5639f2d0b1d99d98c67f39f130662bd1263c216e/src/ghostfat.c#L462-L476
[dropreadback]: https://github.com/zvecr/tinyuf2/blob/3634634babfa468471f8d8fc6c65c388c4b85ff0/src/ghostfat.c#L454-L472
[dropflashsize]: https://github.com/zvecr/tinyuf2/blob/3634634babfa468471f8d8fc6c65c388c4b85ff0/ports/stm32f3/boards/_drop/board.h
[dropmanifest]: https://drop-keyboard-configurator-releases.s3.amazonaws.com/latest.yml
[dropinstaller]: https://drop-keyboard-configurator-releases.s3.amazonaws.com/Drop%20Keyboard%20Configurator%20Setup%2025.5.19-1291.exe
