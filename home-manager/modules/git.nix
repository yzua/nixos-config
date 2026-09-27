# Configure user Git identity, signing, and opt-in secret scanning hooks.

# Keep account-specific identity values in the importing profile.
{ gitIdentity }:
{ config, pkgs, ... }:

{
  programs.git = {
    enable = true;
    # Git itself is already installed system-wide; Home Manager owns the settings.
    package = null;

    # Only universally disposable editor/OS files belong in a global ignore.
    ignores = [
      ".DS_Store"
      "Thumbs.db"
      "*~"
      "*.swp"
      "*.swo"
      ".#*"
    ];

    signing = {
      format = "ssh";
      key = gitIdentity.signingKey;
      signByDefault = true;
    };
    settings.user = {
      inherit (gitIdentity) name email;
    };
    # Provision this user-owned trust file from the public key, outside Nix.
    settings.gpg.ssh.allowedSignersFile = "${config.xdg.configHome}/git/allowed_signers";

    includes = [
      {
        condition = "hasconfig:remote.*.url:https://github.com/**";
        contents.user.email = gitIdentity.githubEmail;
      }
      {
        condition = "hasconfig:remote.*.url:git@github.com:*/**";
        contents.user.email = gitIdentity.githubEmail;
      }
    ];

    hooks.pre-commit = pkgs.writeShellScript "git-pre-commit" ''
      set -eu

      # A repository opts in by placing a Gitleaks config at its root.
      repo_root="$(git rev-parse --show-toplevel)"
      if [ -f "$repo_root/.gitleaks.toml" ]; then
        ${pkgs.gitleaks}/bin/gitleaks git --staged --no-banner --redact \
          --config "$repo_root/.gitleaks.toml" "$repo_root"
      fi

      # A global hooksPath otherwise hides the repository's own hook.
      local_hook="$(git rev-parse --git-common-dir)/hooks/pre-commit"
      if [ -x "$local_hook" ]; then
        "$local_hook" "$@"
      fi
    '';

    hooks.commit-msg = pkgs.writeShellScript "git-conventional-commit-msg" ''
      set -eu

      IFS= read -r subject < "$1" || true
      case "$subject" in
        Merge\ *|Revert\ *|fixup!\ *|squash!\ *|amend!\ *|Initial\ commit) ;;
        *)
          pattern='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|wip)(\([^()]+\))?!?: .+'
          if ! [[ "$subject" =~ $pattern ]]; then
            printf 'Expected a conventional commit: <type>[optional scope][!]: <description>\n' >&2
            printf 'Types: feat fix docs style refactor perf test build ci chore revert wip\n' >&2
            exit 1
          fi
          ;;
      esac

      # core.hooksPath otherwise hides a repository's own commit-msg hook.
      local_hook="$(git rev-parse --git-common-dir)/hooks/commit-msg"
      if [ -x "$local_hook" ]; then
        "$local_hook" "$@"
      fi
    '';
  };
}
