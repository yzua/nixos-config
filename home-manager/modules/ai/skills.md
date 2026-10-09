# Shared skills ownership

`skills.nix` pins the same upstream revisions and prepares their resources during
build/preview. `skills.py` owns source validation, the UI/UX search-path repair,
and local installation. Activation runs only after `linkGeneration`; it does not
clone repositories or repair live skill files.

Installed skills remain writable and owned by skills.sh, not Home Manager.
Before installation, the complete prepared bundle is staged into temporary
writable directories because skills.sh preserves source permissions. Its
`--global --agent '*'` discovery and destination/link policy are unchanged;
unrelated installed skills are not retired by this module.

The UI/UX search command resolves the caller's installed shared copy under
`$HOME/.agents/skills`, not the immutable bundle or temporary staging directory.
Its interpreter comes from the configured Nix Python package.

## Provenance and failure behavior

The prepared bundle's `manifest.json` records original pinned source URLs. Nix
source hashes and this manifest are authoritative. Local global installations
do not refresh skills.sh's remote lock entries; existing entries may be stale.
Use the Nix pins for managed updates rather than treating the old skills.sh lock
as proof of installed contents.

Fetching, missing resources, or a changed UI/UX command fail during preparation,
before activation. All sources are staged before the first installer invocation;
dry runs do not stage or install anything. Installer failures propagate and
temporary sources are cleaned up, but installation is **not transactional**:
skills.sh can leave partial changes or report unsupported global destinations.
This preserves its existing behavior rather than promising rollback it lacks.

Run `python3 -B tests/skills.py` for isolated preparation/installation regressions.
The local-source check uses the managed skills CLI with a temporary home and
network-denying fixtures. Generated activation ordering/dry-run coverage lives
in `tests/config-artifacts.py`; both suites are included in `just test`.
