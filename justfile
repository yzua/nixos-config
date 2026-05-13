# shellcheck disable=SC2148,SC1036,SC1088,SC2121
set shell := ["/usr/bin/env", "bash", "-c"]
set quiet

JUST := "just -u -f " + justfile()
header := "Available tasks:\n"

_default:
    @{{JUST}} --list-heading "{{header}}" --list

# Format all .nix files
format:
    @echo -e "\n➤ Formatting Nix files"
    @nix fmt
    @echo "✔ Formatting passed!"

# Lint all .nix files, bash scripts, and markdown docs (parallel)
lint:
    #!/usr/bin/env bash
    set -euo pipefail
    rc=0

    # Run all four lint groups in parallel (shellcheck and inline-check are independent)
    {{JUST}} _lint-nix > /tmp/lint-nix.log 2>&1 & pid_nix=$!
    {{JUST}} _shellcheck > /tmp/lint-shellcheck.log 2>&1 & pid_sc=$!
    {{JUST}} _inline-check > /tmp/lint-inline.log 2>&1 & pid_ic=$!
    {{JUST}} _lint-markdown > /tmp/lint-markdown.log 2>&1 & pid_md=$!

    wait $pid_nix || rc=$?
    cat /tmp/lint-nix.log
    wait $pid_sc || rc=$?
    cat /tmp/lint-shellcheck.log
    wait $pid_ic || rc=$?
    cat /tmp/lint-inline.log
    wait $pid_md || rc=$?
    cat /tmp/lint-markdown.log

    if [ $rc -ne 0 ]; then exit $rc; fi
    echo "✔ All linting passed!"

# Lint Nix files (statix + deadnix)
_lint-nix:
    @echo -e "\n➤ Linting Nix files…"
    @\time -f "⏱ Statix in %E" statix check --ignore '.git/**' . || nix run nixpkgs#statix -- check --ignore '.git/**'
    @echo -e "\n➤ Checking for dead Nix code…"
    @\time -f "⏱ Deadnix in %E" deadnix --fail . || nix run nixpkgs#deadnix -- --fail .
    @echo "✔ Nix linting passed!"

# Lint shell scripts with ShellCheck
_shellcheck:
    @echo -e "\n➤ Checking Bash scripts…"
    @\time -f "⏱ ShellCheck in %E" find . -name "*.sh" -not -path "./.git/*" -exec shellcheck {} + || find . -name "*.sh" -not -path "./.git/*" -exec nix run nixpkgs#shellcheck -- {} +
    @echo "✔ ShellCheck passed!"

# Lint inline shell scripts embedded in .nix files
_inline-check:
    @echo -e "\n➤ Checking inline Nix shell scripts…"
    @\time -f "⏱ Inline scripts in %E" bash ./scripts/build/shellcheck-nix-inline.sh

# Lint markdown files
_lint-markdown:
    @echo -e "\n➤ Linting Markdown files…"
    @\time -f "⏱ Markdownlint in %E" find . -name "*.md" -not -path "./.git/*" -not -path "*/node_modules/*" -print0 | xargs -0 -r markdownlint || find . -name "*.md" -not -path "./.git/*" -not -path "*/node_modules/*" -print0 | xargs -0 -r nix run nixpkgs#markdownlint-cli --
    @echo "✔ Markdown linting passed!"

# Scan for unused code in .nix files
dead:
    @echo -e "\n➤ Checking for dead Nix code…"
    @\time -f "⏱ Completed in %E" deadnix --fail . || nix run nixpkgs#deadnix -- --fail .
    @echo "✔ Deadnix check passed!"

# Run all shell test suites
test:
    #!/usr/bin/env bash
    set -euo pipefail
    rc=0

    echo -e "\n➤ Running shell tests…"

    REPO_ROOT="$(cd "$(dirname "{{justfile()}}")" && pwd)"
    export REPO_ROOT

    tests=(
        "scripts/build/modules-check-test.sh"
        "scripts/ai/agent-launcher-test.sh"
        "scripts/ai/agent-iter-test.sh"
        "scripts/ai/agent-registry-drift-test.sh"
        "scripts/ai/agents-search-test.sh"
        "scripts/ai/android-re/re-avd-test.sh"
        "scripts/ai/android-re/frida-hooks-test.sh"
        "scripts/system/report/report-collectors-test.sh"
    )

    for t in "${tests[@]}"; do
        if bash "$REPO_ROOT/$t"; then
            echo "  ✔ $t"
        else
            echo "  ✗ $t"
            rc=1
        fi
    done

    if [ $rc -ne 0 ]; then exit $rc; fi
    echo "✔ All tests passed!"

# Run nix flake check
check:
    @echo -e "\n➤ Running nix flake check…"
    @\time -f "⏱ Completed in %E" nix flake check --no-build path:.
    @echo "✔ Flake check passed!"

# Check all missing imports
modules:
    @echo -e "\n➤ Checking modules"
    @\time -f "⏱ Completed in %E" bash ./scripts/build/modules-check.sh

# Check for duplicate packages and program/module conflicts
pkgs:
    @echo -e "\n➤ Checking packages"
    @\time -f "⏱ Completed in %E" bash ./scripts/build/packages-check.sh

# Switch Home-Manager generation
home:
    @echo -e "\n➤ Switching Home-Manager…"
    home-manager switch --flake path:.#yz@desktop -b backup

# Build Home-Manager generation without switching
home-build:
    @echo -e "\n➤ Building Home-Manager generation…"
    nix build 'path:.#homeConfigurations."yz@desktop".activationPackage' -o result-home

# Build NixOS generation without switching
nixos-build:
    @echo -e "\n➤ Building NixOS generation…"
    nix build path:.#nixosConfigurations.desktop.config.system.build.toplevel -o result-nixos

# Switch NixOS generation
nixos:
    @echo -e "\n➤ Rebuilding NixOS…"
    sudo nixos-rebuild switch --flake 'path:.#desktop'

# Build pending generations and show package/service drift before switching
deploy-preview:
    #!/usr/bin/env bash
    set -euo pipefail
    {{JUST}} nixos-build
    {{JUST}} home-build
    echo -e "\n➤ Pending NixOS diff"
    nvd diff /run/current-system ./result-nixos
    echo -e "\n➤ Pending Home-Manager diff"
    current_home="/nix/var/nix/profiles/per-user/yz/home-manager"
    if [ -e "$current_home" ]; then
        nvd diff "$current_home" ./result-home
    else
        echo "⚠ Current Home Manager profile not found: $current_home"
    fi

# All of the above, in order (fast checks parallel, then build steps)
all:
    #!/usr/bin/env bash
    set -euo pipefail
    JUST="{{JUST}}"
    rc=0

    echo -e "\n➤ Running full pipeline…"

    # Phase 1: Fast checks in parallel (modules, pkgs, lint)
    $JUST modules > /tmp/pipeline-modules.log 2>&1 & pid_mod=$!
    $JUST pkgs > /tmp/pipeline-pkgs.log 2>&1 & pid_pkgs=$!
    $JUST lint > /tmp/pipeline-lint.log 2>&1 & pid_lint=$!

    wait $pid_mod || { rc=$?; echo "✗ modules failed"; }
    cat /tmp/pipeline-modules.log
    wait $pid_pkgs || { rc=$?; echo "✗ pkgs failed"; }
    cat /tmp/pipeline-pkgs.log
    wait $pid_lint || { rc=$?; echo "✗ lint failed"; }
    cat /tmp/pipeline-lint.log
    if [ $rc -ne 0 ]; then exit $rc; fi

    # Phase 2: Sequential (format depends on lint, check evaluates everything)
    $JUST format
    $JUST test
    $JUST check
    $JUST deploy-preview
    $JUST nixos
    $JUST home
    echo -e "✔ All done!"

# Generate system health report
report mode="full":
    sudo system-report {{mode}}

# View latest system report
report-view type="full":
    system-report {{ if type == "errors" { "view-errors" } else { "view" } }}

# Show what changed between current and previous NixOS generation
diff:
    @echo -e "\n➤ Diffing NixOS generations…"
    nvd diff $(ls -dv /nix/var/nix/profiles/system-*-link | tail -2)

# Update all flake inputs (runs pre-check, updates, then post-check)
update:
	#!/usr/bin/env bash
	set -euo pipefail
	JUST="{{JUST}}"
	echo -e "\n➤ Pre-update health check…"
	$JUST check
	echo -e "\n➤ Updating flake inputs…"
	nix flake update
	echo -e "\n➤ Post-update verification…"
	$JUST check
	echo -e "✔ Update complete!"

# Full upgrade pipeline: update inputs → build NixOS → build Home Manager → verify
upgrade:
	#!/usr/bin/env bash
	set -euo pipefail
	JUST="{{JUST}}"
	echo -e "\n➤ Full system upgrade…"
	$JUST update
	$JUST nixos
	$JUST home
	echo -e "\n➤ Post-upgrade health check…"
	$JUST security-audit
	echo -e "✔ Full upgrade complete!"

# Clean up build artifacts and caches
clean:
	@echo -e "\n➤ Cleaning up build artifacts and caches…"
	@echo "[DEL] Cleaning Nix store (1 day older)..."
	nh clean all --keep 1
	@echo "[HM] Cleaning Home Manager generations..."
	home-manager expire-generations "-1 days"
	@echo "[OPT] Optimizing Nix store..."
	nix store optimise
	@echo -e "✔ Cleanup completed!"

# Install repo-local git hooks for NixOS-specific validation.
# Global hooks (secrets, signing, conventional commits) are managed by Home Manager.
# Repo-local hooks chain after global hooks via core.hooksPath.
install-hooks:
    @cp scripts/build/pre-commit-hook.sh .git/hooks/pre-commit
    @chmod +x .git/hooks/pre-commit
    @cp scripts/build/pre-push-hook.sh .git/hooks/pre-push
    @chmod +x .git/hooks/pre-push
    @echo "✔ Repo-local pre-commit and pre-push hooks installed!"

# Audit systemd unit security exposure
security-audit:
    @echo -e "\n➤ Auditing systemd unit hardening…"
    @systemd-analyze security --no-pager 2>/dev/null | grep -E "EXPOSED|UNSAFE" || echo "✔ No EXPOSED/UNSAFE units found"
    @echo -e "\n➤ Running vulnix on system closure…"
    @if command -v vulnix >/dev/null 2>&1; then \
        mkdir -p /tmp/system-security-audit; \
        if timeout 90s vulnix --system > /tmp/system-security-audit/vulnix.log 2>&1; then \
          cat /tmp/system-security-audit/vulnix.log; \
        else \
          status=$?; \
          cat /tmp/system-security-audit/vulnix.log; \
          if [ $status -eq 124 ]; then \
            echo "⚠ vulnix timed out after 90s; partial log: /tmp/system-security-audit/vulnix.log"; \
          else \
            echo "⚠ vulnix found advisories or failed (exit $status); log: /tmp/system-security-audit/vulnix.log"; \
          fi; \
        fi; \
      else \
        echo "⚠ vulnix not available (run 'just home' first)"; \
      fi

# Edit secrets with SOPS (uses RAM-backed tmpfs for security)
sops-edit:
	@echo -e "\n➤ Editing secrets with SOPS…"
	@status=0; ./scripts/sops/sops-edit.sh || status=$?; if [ $status -eq 200 ]; then echo "No changes made."; elif [ $status -ne 0 ]; then exit $status; fi

# View decrypted secrets (read-only)
sops-view:
	@echo -e "\n➤ Viewing decrypted secrets…"
	@nix run nixpkgs#sops -- --decrypt secrets/secrets.yaml

# Add a single secret (prompts securely to avoid process list exposure)
secrets-add key:
	@echo "{{key}}" | grep -qE '^[a-zA-Z_][a-zA-Z0-9_]*$$' || (echo "✗ Invalid key name. Use alphanumeric characters and underscores only." && exit 1)
	@read -s -p "Enter secret value for '{{key}}': " VALUE && echo "" && \
	nix run nixpkgs#sops -- --set "[\"{{key}}\"] \"$VALUE\"" secrets/secrets.yaml && \
	echo "✔ Secret added!"
