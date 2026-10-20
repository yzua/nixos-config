---
name: samsung-tv
description: Identify or pair the configured Samsung TV, read/set exact volume, send requested remote buttons, or launch a configured TV app using pi-home's on-demand CLI.
---

# Samsung TV

Use `pi-home tv --help` for the command surface. The managed configuration selects the LAN device and permitted apps; credentials stay in the caller's private state directory.

1. Establish the requested scope. A connection-only request permits `pi-home tv connect`, which sends no buttons but may show a pairing prompt. Let the user approve that prompt. `pi-home tv info` reads basic device identity without pairing.
2. For an explicitly requested button, run `pi-home tv key <name> --execute` once. For an explicitly requested app, use `pi-home tv launch <configured-name> --execute`. See the help for the allowed names. If pairing is missing, ask before the separate connect operation.
3. For volume, `pi-home tv volume` reads the numeric level. A requested exact level uses `pi-home tv volume <0-100> --execute`, which performs at most one set and verifies read-back. Confirm maximum volume 100 explicitly because it can be extremely loud. Preserve mute/playback; use numeric read-back rather than blind volume-up sequences. A mismatch/timeout is uncertain: read status before considering another mutation.
4. Report the actual result: authorization succeeded, a button/app command was sent, or an exact volume was verified. Each invocation closes its socket. Confirm a visible result with the user before further navigation.

## Observation boundary

This API has no screenshots, UI tree, current-focus observation or reliable global foreground-app state. Work from the user's fresh description or screenshot; avoid blind multi-button sequences and automatic retries. A timeout leaves the action outcome uncertain.

Keep app debugging, SDB/root access, firmware/service-menu keys, installation/reset, account changes and network-policy changes outside this workflow. App launch is normal launch, not a debugger restart. Preserve TV app data and Samsung certificates. Use the managed CLI rather than raw remote keys or an always-connected service. Never display the pairing token, token-bearing URL, raw authorization events or library debug logs.
