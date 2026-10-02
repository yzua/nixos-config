set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default:
    @just --list

# Evaluate the flake without building or activating it.
verify:
    nix flake check --no-build --no-write-lock-file .

# Evaluate both configs and flag Nix files Git flakes cannot see yet.
check:
    @untracked="$(git ls-files --others --exclude-standard -- '*.nix')"; \
      if [ -n "$untracked" ]; then \
        printf 'Warning: Git flakes ignore untracked .nix files. Stage new files you want evaluated:\n%s\n' "$untracked"; \
      else \
        echo "No untracked Nix files."; \
      fi
    @just verify

# Format Nix, shell, TypeScript, Python, Markdown, and the command menu (modifies files).
fmt:
    nix fmt --no-write-lock-file
    biome format --write .
    ruff check --select I --fix --no-cache .
    ruff format --no-cache .
    rumdl fmt --no-cache .
    just --fmt

# Read-only formatting check for all supported languages and the justfile.
fmt-check:
    @git ls-files -z --cached --others --exclude-standard -- '*.nix' ':(exclude)hardware-configuration.nix' ':(exclude,glob)**/hardware-configuration.nix' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then nixfmt --check "$file"; fi; done
    @git ls-files -z --cached --others --exclude-standard -- '*.sh' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then shfmt -d -i 2 "$file"; fi; done
    biome format .
    ruff format --check --no-cache .
    rumdl fmt --check --no-cache .
    just --fmt --check

# Fast static analysis; run in the dev shell if these tools are not installed.
lint:
    statix check --ignore 'hardware-configuration.nix' --ignore '**/hardware-configuration.nix' .
    @git ls-files -z --cached --others --exclude-standard -- '*.nix' ':(exclude)hardware-configuration.nix' ':(exclude,glob)**/hardware-configuration.nix' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then deadnix --fail -- "$file"; fi; done
    @just lint-shell
    @just lint-ts
    @just lint-python
    @just lint-markdown

# Fast Bash error checking without running the other language checks.
lint-shell:
    @git ls-files -z --cached --others --exclude-standard -- '*.sh' | \
      while IFS= read -r -d '' file; do if [ -f "$file" ]; then shellcheck -x "$file"; fi; done

# Fast TypeScript error checking without running the other language checks.
lint-ts:
    biome lint --diagnostic-level=warn --error-on-warnings .

# Fast Python error and import checking without running the other language checks.
lint-python:
    ruff check --no-cache .

# Fast Markdown checks for syntax, links, and rendering mistakes.
lint-markdown:
    rumdl check --no-cache .

# Run isolated offline regressions; no activation, live desktop/lab, or paid calls.
test:
    @bash scripts/test.sh

# Prove preview retention with GC only in a fresh disposable local Nix store.
test-preview-roots-gc:
    @bash tests/preview-roots-gc.sh

# Show the desired, saved preview, and active system/home generations (no build or switch).
status:
    @./scripts/status.sh

# Build and compare the system, then retain its saved preview build.
preview:
    @./scripts/generation.sh preview system

# Activate exactly the built closure; run `just preview` and review it first.
switch:
    @./scripts/generation.sh switch system

# Build and compare Home Manager, then retain its saved preview build.
home-preview:
    @./scripts/home-preview.sh

# Explicitly activate this user's Home Manager config (never run with sudo).
home-switch:
    @./scripts/home-switch.sh
