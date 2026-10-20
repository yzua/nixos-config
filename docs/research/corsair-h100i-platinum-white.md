# Corsair H100i Platinum: pump white differs from fan white

Investigated 2026-10-19. This is an evidence note, not a confirmed hardware diagnosis.
No firmware update or cooling initialization was performed.

## Local evidence

- USB `1b1c:0c18` identifies the H100i Platinum. A standard status request reports
  firmware **1.1.15**. The pinned liquidctl 1.16.0 driver supports this model and
  warns about firmware older than 1.1.0, not this version.
- The intended mapping is 16 pump/block LEDs followed by eight stock-fan LEDs.
  OpenRGB's fan zone initially had zero LEDs; resizing to eight persisted across
  relaunches. Both fans subsequently appeared white to the user.
- With OpenRGB closed, resetting only liquidctl's software `leds_enabled` cache
  and setting fixed `FFFFFF` produced **five expected lighting writes**, with
  **no checksum warnings**. This was not `initialize` and did not write cooling
  settings. The block still appeared tinted relative to the fans.
- A human-observed test set the first 16 LEDs to red, green and blue separately,
  keeping the remaining eight white. The block responded to all three primaries.
  This confirms responsiveness, not equal channel intensity or accurate white.
- Initial `C0C0FF` compensation was inconclusive. Later, whole-block `4040FF`
  still appeared yellow, while **`0808FF` (8/8/255) appeared white to the user but
  dim**. Raising red/green to 12 and 16 made it yellowish again. The confirmed
  8/8/255 correction is now the configured login setting; the fan LEDs remain
  `FFFFFF`. Blue is already at its maximum, so raising only red/green increases
  output while reintroducing the tint. This is compensation, not a proven repair.
- The GPU's separate exact-ID experiment ultimately produced user-confirmed white;
  that outcome does not diagnose the unrelated Corsair block's white imbalance.

The intended mapping, color commands and model limits are documented in the
[pinned lighting guide][guide] and [driver][driver]. OpenRGB's
[constructor/destructor][openrgb] change lighting routing on startup/shutdown;
its shutdown can restore hardware effects. liquidctl's full lighting-enable
sequence restores the same software mapping, provided its cached flag is reset.
This explains possible tool-interoperability effects, but does not establish the
cause of the remaining tint after the fresh-enable test.

## Matching reports

The strongest match is Corsair's own forum thread
[“H100i Platinum isn't displaying the correct colors”][exact-forum] (2022):

> “When you enable just white on the h100i its yellow … All my corsair fans can
> do white but the lights on the h100i.”

A community member suggests static-color correction in iCUE. There is no
confirmed resolution or Corsair-employee diagnosis in that thread. Importantly,
this report concerns Corsair's own software, not a Linux-only driver failure.

A [related H115i Platinum report][related-forum] says `255/255/255` appears yellow
and attempted correction yields yellow/green instead. Community members discuss
LED/diffuser white balance and potentially insufficient blue intensity. A
**Corsair employee directs the owner to support**, but does not diagnose a failed
LED or firmware bug. This is a related model, not an exact H100i match. A member's
suggestion to force-flash firmware is unverified and is not recommended here.

An [exact-model first-person report][report] describes an H100i Platinum set to
white whose pump looks yellowish. A commenter reports the same issue after about
two years, with an RMA replacement producing normal white. A separate commenter
reports replacement of the related Platinum SE for the same symptom.

These are anecdotes, not a manufacturer recall or a controlled diagnosis. They
show the symptom is not unique to this workstation; they do not prove this unit
has the same failure.

## GitHub/GitLab software evidence

- [liquidctl issue #190][issue190] concerns H100i Platinum firmware 1.1.15, but
  the symptom is moving/marquee lighting instead of fixed colors. The investigator
  confirmed correct color payloads but a missing static-mode enable sequence.
  [Fix #194][fix194] added that sequence; [release 1.4.2][release142] explicitly
  lists the fix. It is already in installed 1.16.0 and the local fresh-enable
  test exercised it. This is not evidence of an unfixed steady-white-tint bug.
- [OpenRGB issue #1539][issue1539] reports colors too red/dim or shifting between
  correct and incorrect, with iCUE consistently correct. It is **H100i RGB Pro
  XT**, not Platinum, and describes an intermittent symptom. No confirmed fix
  was found on its public page. It is evidence that related software color
  problems exist, not a diagnosis of this unit.
- OpenRGB's GitHub repository is a mirror with issues disabled; the real GitLab
  tracker was also checked. No confirmed released fix matching this exact steady
  tint was found. This is a search result, not proof that no such bug can exist.

## Manufacturer guidance

Corsair's [RGB LED testing article][testing] recommends static true white followed
by individual red, green and blue tests. It says **dimness, flickering or failure
to illuminate** in a primary color supports a hardware issue. Merely seeing each
primary does not establish equal brightness. The article is categorized under
keyboards, so use it as general RGB diagnostic guidance, not a cooler-specific
service bulletin.

Corsair's separate [fan LED-failure article][failure] recognizes discoloration and
recommends troubleshooting followed by support where appropriate. Its fan-chain
and connection instructions should not be blindly applied to a pump block.

## Practical interpretation

The same visible symptom is reported outside Linux, including the exact model,
but the reports do not establish a single universal cause or a proven firmware
repair. A weak/imbalanced RGB component or an optical difference remains plausible.
The later successful 8/8/255 compensation supports a relative RGB-output imbalance,
but does not establish whether LEDs, optics, factory variation or another cause
is responsible. The large correction and reduced white brightness are relevant
facts for a vendor support request. The
available visual observations do **not** prove a failed LED, and successful USB
writes do **not** prove a physical white-point match.

Do not treat firmware flashing, cooler initialization, speculative register
writes, or repeated RGB guessing as established fixes. If Windows/iCUE is already
available, checking static `255,255,255` there provides a useful independent
software comparison. If the tint remains, contact Corsair with the model,
firmware and comparative photos/video; warranty eligibility must be checked, not
assumed. If iCUE produces a clearly correct white on the same hardware but the
isolated Linux test does not, gather a narrow upstream driver report instead.
For the current Linux-only setup, a [vendor support draft](corsair-h100i-platinum-support-draft.md)
records the facts and completed tests without assuming a hardware diagnosis. It
has not been submitted; serial/receipt details belong only in the private portal.

[guide]: https://github.com/liquidctl/liquidctl/blob/v1.16.0/docs/corsair-platinum-pro-xt-guide.md#controlling-the-leds
[driver]: https://github.com/liquidctl/liquidctl/blob/v1.16.0/liquidctl/driver/hydro_platinum.py
[openrgb]: https://github.com/CalcProgrammer1/OpenRGB/blob/release_candidate_1.0rc3/Controllers/CorsairHydroPlatinumController/CorsairHydroPlatinumController.cpp
[report]: https://www.reddit.com/r/Corsair/comments/mtulzb/
[exact-forum]: https://forum.corsair.com/forums/topic/179666-h100i-platinum-isnt-displaying-the-correct-colors/
[related-forum]: https://forum.corsair.com/forums/topic/178878-h115i-rgb-platinum-block-white-is-yellow/
[issue190]: https://github.com/liquidctl/liquidctl/issues/190
[fix194]: https://github.com/liquidctl/liquidctl/pull/194
[release142]: https://github.com/liquidctl/liquidctl/releases/tag/v1.4.2
[issue1539]: https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/1539
[testing]: https://help.corsair.com/hc/en-us/articles/13681032341133-Keyboards-Testing-RGB-LEDs-For-Your-Device
[failure]: https://help.corsair.com/hc/en-us/articles/25400260749709-Fans-LED-Failure
