# Support draft: H100i Platinum pump white differs from fan white

**Status:** draft only; not submitted. Send receipt, serial/lot codes and account
information privately through [Corsair Support](https://help.corsair.com/), not
through this repository or a public issue.

Portal attempt: the old request form now directs users to Corsair's AI chat. The
user approved its privacy-policy gate and a technical-only summary. The chat
returned HTTP 403 and a conversation-recovery error; no formal ticket confirmation
was received. No account, email, serial or receipt information was entered. A
manual retry in the user's normal browser is the next handoff, not a submitted
support request.

## Subject

H100i RGB Platinum: pump/block is tinted at RGB 255/255/255 while both fans are white

## Message

My Corsair Hydro H100i Platinum has a steady non-white/tinted appearance on the
pump/block when configured to RGB `255,255,255`. Both RGB fans appear white.

Hardware and software:

- H100i Platinum USB vendor/product ID: `1b1c:0c18`.
- Firmware: **1.1.15**, read from the normal status response.
- OS: NixOS/Linux; no Windows installation available for an iCUE comparison.
- Tested with liquidctl **1.16.0** and OpenRGB **1.0rc3**.
- Mapping: 16 pump LEDs and eight LEDs across the two stock RGB fans.

Tests already performed:

1. Closed OpenRGB before testing with liquidctl, to avoid concurrent control.
2. Reset only liquidctl's software lighting-enable cache and reapplied fixed
   `FFFFFF`. Debug output showed the three lighting-enable packets plus two color
   packets, with no checksum warnings.
3. Tested the 16 pump LEDs with static red, green and blue independently, while
   keeping the fan LEDs white. The pump responded to all three primaries.
   Relative channel brightness has not been measured.
4. Restored `FFFFFF` to all 24 LEDs. The pump still does not visually match the
   fans' white.
5. Further pump-only white-balance testing found that **8/8/255** appears neutral
   white, but is much dimmer than the fans. Raising red and green to 12 and 16
   reintroduced a yellowish tint; blue was already at maximum 255. This correction
   is a workaround, not a demonstrated repair or diagnosis of a failed component.

No firmware update, cooling initialization, pump-mode change, fan-curve change or
RAM/CPU/GPU clock change was performed for this test. The pump's normal status
telemetry remains available.

A similar exact-model symptom was reported on your forum:
[H100i Platinum isn't displaying the correct colors](https://forum.corsair.com/forums/topic/179666-h100i-platinum-isnt-displaying-the-correct-colors/).

Could you advise whether this warrants inspection of pump LED output/white
balance, whether there is an official lighting-only diagnostic procedure, and
whether the unit qualifies for service under its purchase/warranty terms?
Please identify any proposed procedure that would reset cooling settings before
we attempt it.

I can supply purchase information and any available photos/video privately.
