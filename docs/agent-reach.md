# Agent Reach

Home Manager installs Agent Reach **1.6.0** from the official GitHub release, with
its tested OpenCLI **1.8.7** and extension **1.0.23** pinned by hash. Python
libraries, Node and Google Chrome come from the existing Nixpkgs pin; no uv or
PyPI installation of Agent Reach is used. The Python package named `agent-reach`
on PyPI is unrelated to this project.

## Testing X and Reddit

```sh
agent-reach version
agent-reach add reddit
agent-reach add twitter
agent-reach reddit search 'NixOS' --limit 2 --backend public-web
agent-reach reddit search 'NixOS' --limit 2 --backend opencli
agent-reach twitter search 'NixOS' --limit 2 --backend opencli
```

`public-web` searches indexed public content; it is not native site search and
may return old or incomplete results. Once a channel is added, normal searches
use its site adapter; select `--backend public-web` explicitly to use indexing.
Native platform access may fail because of login requirements, challenges,
rate limits or upstream changes. A JSON parse failure is not proof that login
is required.

If a command actually requires authentication, open the dedicated browser and
log in yourself, preferably using a secondary account:

```sh
agent-reach login twitter
agent-reach login reddit
```

Passwords and cookies must not be pasted into chat. The Nix package disables
automatic imports from other browser sessions for these browser-backed queries;
`login CHANNEL --import-existing` still explicitly requests an import. The
separate dedicated profile and saved sessions remain under `~/.agent-reach/`,
not in the repository or Nix store. The OpenCLI extension is only loaded in this
dedicated browser, not installed into your everyday browser. The browser and
bridge listen on loopback ports 9222 and 19825; do not expose them remotely.

```sh
agent-reach browser status
agent-reach browser stop
agent-reach logout twitter
agent-reach logout reddit
```

## Ownership and limits

Update package versions and hashes through Nix, then run `just check` and
`just home-preview`. Review the preview before running `just home-switch`.
Do **not** use the upstream
`agent-reach update`, `setup`, or skill installer for this managed installation:
those commands can install mutable dependencies and write shared agent skills.
No Agent Reach skill is installed by this module; existing skills retain their
current owner.

Only the X/Reddit browser prerequisites are bundled here. Other channels may
need extra packages, keys or their own reviewed setup. This package selects the
managed system Chrome instead of downloading CloakBrowser and uses a pinned
extension instead of fetching the latest release. These are small downstream
changes, covered by the package's offline tests. Existing browser-detection,
CAPTCHA and platform restrictions still apply. OpenCLI itself includes write
commands; Agent Reach exposes the narrower read/search interface. Installation
does not authorize posting, account actions or importing credentials.

Build and test the package independently with:

```sh
nix build .#agent-reach --no-link
```

Removing the Home Manager package does not delete private runtime state. Stop
its browser before separately reviewing and deleting `~/.agent-reach/` if you
want to remove saved sessions too.
