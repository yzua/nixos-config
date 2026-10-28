# Shared skills ownership

`skills.nix` pins upstream revisions (sharing the unchanged Chrome source descriptor
from `pi-base/chrome-skill.nix` with Pi base) and includes repository-owned skills from
`skills/`, preparing their resources during build/preview. `skills.py` owns source
validation, the UI/UX search-path repair, and local installation. Activation runs
only after `linkGeneration`; it does not clone repositories or repair live skill
files.

The pinned `karpathy-guidelines` skill provides the full upstream coding guidelines
for all discovered agents. Invoke it by name when writing, reviewing, or refactoring
code. Pi's global instructions also include a concise adaptation, so its core coding
discipline applies without loading the skill.

The pinned `impeccable` skill uses the released `.agents` distribution for shared
installation, including its command references and supporting resources.
`impeccable-skill.nix` pins the official static Linux engine and replaces the launcher
to use that immutable Nix path, resolve resources from the installed skill directory,
and disable optional telemetry. It performs no runtime engine downloads and installs
no provider hooks. Shared workflow references delegate to generic subagents using
bundled role briefs rather than requiring provider-specific agent registrations.
Invoke it by name, for example: “Use impeccable to audit this interface.”
Browser-backed commands still need a locally available browser. Update
its skill and engine pins through Nix rather than the upstream self-updater.

The local [app-design skill](skills/app-design/SKILL.md) connects product context,
layout exploration, implementation, and browser critique for web apps and
dashboards. Invoke it by name, for example: “Use app-design to improve this
dashboard.” It uses relevant installed skills and the app's existing tooling.

Installed skills remain writable and owned by skills.sh, not Home Manager.
Before installation, the complete prepared bundle is staged into temporary
writable directories because skills.sh preserves source permissions. Its
`--global --agent '*'` discovery and destination/link policy are unchanged;
unrelated installed skills are not retired by this module. With skills.sh 1.7.2,
Pi uses the shared `~/.agents/skills` directory directly (supported by Pi 1.1.0);
other agents such as Claude still receive installer-owned symlinks. Pi's explicit-load
Base/Home/RE profiles also select the pinned Chrome skill directory directly, including
its references; they do not take ownership of or rewrite these mutable installations.

The UI/UX search command resolves the caller's installed shared copy under
`$HOME/.agents/skills`, not the immutable bundle or temporary staging directory.
Its interpreter comes from the configured Nix Python package.

## Provenance and failure behavior

The prepared bundle's `manifest.json` records original pinned upstream URLs or
`repo:` identifiers for repository-owned skills. Upstream hashes and the captured
repository source in the Nix store determine the prepared contents. Stage new
local skill files before evaluation or preview so Git flakes include them.
Local global installations do not refresh skills.sh's remote lock entries;
existing entries may be stale. Use the managed sources rather than treating the
old skills.sh lock as proof of installed contents.

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
