# OpenRGB support draft: MSI RTX 2070 exact PCI tuple missing

**Status:** draft only; not submitted. Initially a support/identification
request; subsequently updated with an explicitly approved, successful exact-ID
hardware experiment on this particular card. This is not an upstream-wide
compatibility guarantee or a neighboring-ID spoof.
Do not include serial numbers, GPU UUIDs or account credentials in a public issue.

## Suggested title

MSI RTX 2070 `10de:1f07 / 1462:3733`: guidance for exact-device RGB support

## Observed hardware

| Field | Value |
| --- | --- |
| GPU name | NVIDIA GeForce RTX 2070 |
| PCI vendor/device | `10de:1f07` |
| Subsystem vendor/device | `1462:3733` |
| VBIOS version | `90.06.18.80.DA` |
| NVIDIA driver | `595.71.05` |
| OS | NixOS/Linux |
| OpenRGB tested | 1.0rc3 |

The goal is static-white GPU lighting only. No fan, clock, voltage, VBIOS or
firmware changes are requested. There is no Windows installation available for
an MSI Mystic Light comparison.

## Source observation

The [MSI GPU detector][detector] registers these neighboring combinations:

- MSI RTX 2070 Gaming: `10de:1f02 / 1462:3733`.
- MSI RTX 2070 Gaming Z: `10de:1f07 / 1462:3732`.

The actual `10de:1f07 / 1462:3733` tuple is not registered in either pinned
1.0rc3 or upstream commit `7182807a288a9e8107a84fbebc44239677f1ea24` examined during
this investigation. The registered MSI controller uses NVIDIA I2C adapter port 1
and address `0x68`. This describes existing supported hardware; it does not prove
this unit's controller or address.

The ordinary local launcher intentionally exposes only independently supported
USB lighting controllers, not GPU I2C nodes. This exclusion is a safety boundary,
not an assertion that passing a different card's PCI ID would work.

## Validation limitation

The existing v1 detector/controller has no chip-signature, firmware-version or
capability gate before exposing lighting operations. Its initial reads assume
that the registered address uses the expected register map. A failed SMBus read
can become `0xff` through the controller's unsigned return type, so merely making
a controller appear in the UI would not prove compatibility.

Setting a color also writes an undocumented register (`0x26 = 0`), in addition
to RGB state. Source review does not show deliberate GPU clock/voltage or firmware
programming, but it cannot establish what those writes do on an unidentified
endpoint. A successful ACK or plausible state read is not a unique chip identity.
Therefore an exact-tuple patch needs actual controller/routing evidence, not just
a detector addition or an assumed-safe register read.

## Alternatives checked

No maintained Linux tool with verified support for this exact tuple was found:

- [Prism RGB's actual MSI GPU allowlist][prism] covers only RTX 3080 Gaming X Trio
  `10de:2206 / 1462:3892`, not this card.
- [liquidctl's NVIDIA guide][liquidctl] covers selected ASUS/EVGA controllers,
  not this MSI model.
- [msi-rgb][msirgb] is a motherboard/Super-I/O tool, not this GPU's controller.
- [nvidia-led][nvidialed] is not an arbitrary RGB-color solution for this card.

These negative search results do not prove that no private or future solution
exists. They do mean that another package cannot currently be recommended as a
verified static-white workaround. The appropriate next step is an upstream
[new-device request][template], not a forced neighboring device identity.

## Requested maintainer guidance

1. Is this exact tuple a known MSI Gaming board variation or a different lighting
   controller/revision?
2. What non-mutating identification evidence can distinguish it before enabling
   an existing driver's writes?
3. If a detector addition is appropriate, which exact controller implementation
   and validation procedure should be used?

## Separate experimental build (not a hardware validation)

The user approved compilation of a separate exact-ID experiment. A derivative
of the actually selected OpenRGB 1.0rc3 was built successfully with one additional
registration for the real `10de:1f07 / 1462:3733` tuple. Existing MSI registrations
were retained. Unrelated controller sources were omitted to limit build cost;
Nanoleaf pairing helper code required by the GUI remained, but its detector was
omitted. No installed package or managed configuration was replaced.

The experimental package is retained under the caller's state directory:
`${XDG_STATE_HOME:-$HOME/.local/state}/nixos/gpu-rgb-experiment/package`. Its
reproducible Nix recipe is alongside it in `build.nix`.

Hardware-hidden checks confirmed the new detector exists and all other 76
registered detector entries can be disabled. **The offline run still listed a
placeholder MSI controller despite having no I2C/NVIDIA/HID/raw-memory nodes.**
The stock Linux bus enumerator retains adapters after failed device opens, and
the MSI detector constructs controllers without validating read success. Thus a
new UI entry cannot be treated as evidence of communication or compatibility.
A guarded, separately authorized state-read test is needed before any possible
lighting-write test. No GPU bus access was authorized for the build step.

## Approved hardware experiment and result

After the separate build step, the user explicitly approved a narrowly scoped
state read, then separately approved a white-setting test. Both used only the
verified NVIDIA port-1 character device, after checking all four PCI IDs,
`nvidia` driver, adapter name and sysfs major/minor. No force-address ioctl or
user bus ACL was used.

A signed-error-preserving SMBus read helper obtained:

| Register state | Before | After |
| --- | --- | --- |
| Mode | `0x08` (rainbow) | `0x13` (static/Direct) |
| Brightness | 80 | 80 |
| Speed encoding | `0x02` | `0x02` |
| RGB1 | `FFFFFF` | `FFFFFF` |
| RGB2 | `0000E0` | `0000E0` |
| RGB3 | `00E000` | `00E000` |

The experimental binary applied **Direct / FFFFFF / brightness 80**, with every
other detector disabled and only that adapter exposed. No save, firmware, fan,
clock or voltage command was sent. The user **confirmed the GPU became steady
white**. Temporary `i2c-dev` access was removed afterward. These observations
validate the tested lighting path on this particular unit; successful state
reads alone would not have done so.

The user then approved automatic boot restoration. The managed derivative's
`drvPath` matches the successful test build exactly:
`/nix/store/7rqpjai5y7n4gf23yyx0d484pzvsjjni-openrgb-exact-gpu-validation-1.0rc3.drv`.
Its resulting executable is retained independently of the regular OpenRGB app.
The boot helper validates signed reads, skips an already-correct state, otherwise
applies the same settings and verifies mode/RGB1/brightness while checking speed
and RGB2/RGB3 remained unchanged. It serializes after RAM startup, never saves,
and does not make GPU I2C generally accessible to the user.

No generic GPU-bus scan, neighboring-ID spoof, or GPU firmware operation was
performed. The existing driver's undocumented-register write remains a reason
to keep this device-specific experiment scoped rather than advertise universal
MSI compatibility.

Relevant implementation: [controller register access][controller] and
[RGB update methods][updates].

[detector]: https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/MSIGPUController/MSIGPUController/MSIGPUControllerDetect.cpp
[controller]: https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/MSIGPUController/MSIGPUController/MSIGPUController.cpp
[updates]: https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/MSIGPUController/MSIGPUController/RGBController_MSIGPU.cpp
[prism]: https://github.com/HoneyBadger614/prism-rgb/blob/d883fe9a545ed32a17e134697837596b13f8fe95/crates/prism-core/src/msi_gpu.rs
[liquidctl]: https://github.com/liquidctl/liquidctl/blob/main/docs/nvidia-guide.md
[msirgb]: https://github.com/nagisa/msi-rgb
[nvidialed]: https://github.com/Madh93/nvidia-led
[template]: https://github.com/CalcProgrammer1/OpenRGB/blob/master/.gitlab/issue_templates/New%20Device.md
