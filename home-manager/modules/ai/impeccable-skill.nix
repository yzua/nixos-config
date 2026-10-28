# Prepare the released shared Impeccable skill with a pinned engine and no runtime downloads.
{ pkgs }:
let
  version = "4.8.0";
  engineVersion = "0.1.18";
  platform =
    {
      x86_64-linux = {
        asset = "linux-x64";
        hash = "sha256-c27XhedK4jRNMDYSf2FN3eWrUgpSfYvIKokWEu9x9kg=";
      };
      aarch64-linux = {
        asset = "linux-arm64";
        hash = "sha256-MXyxjWSw93FWgd1uV0rWSyrbWmyvjnobO1eWX4BUBL4=";
      };
    }
    .${pkgs.stdenv.hostPlatform.system};
  archive = pkgs.fetchurl {
    url = "https://github.com/pbakaus/impeccable/releases/download/skill-v${version}/universal.zip";
    hash = "sha256-gub2/zorGPRvDy/DiMGrer88zFK7/FIkVjltEwEdZwY=";
  };
  engineSource = pkgs.fetchurl {
    url = "https://github.com/pbakaus/impeccable/releases/download/engine-v${engineVersion}/impeccable-${platform.asset}";
    inherit (platform) hash;
  };
  # Official Linux engines are static musl binaries; no foreign loader is needed.
  engine = pkgs.runCommand "impeccable-engine-${engineVersion}" { } ''
    install -Dm755 ${engineSource} "$out/bin/impeccable"
  '';
  launcher = pkgs.writeShellScript "impeccable" ''
    export IMPECCABLE_SKILL_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
    export IMPECCABLE_SELF="$0"
    export IMPECCABLE_NO_TELEMETRY=1
    exec ${engine}/bin/impeccable "$@"
  '';
in
{
  path =
    pkgs.runCommand "impeccable-skill-${version}"
      {
        nativeBuildInputs = [ pkgs.unzip ];
      }
      ''
        unzip -q ${archive} '.agents/skills/impeccable/*'
        mkdir -p "$out"
        cp -R .agents/skills/impeccable/. "$out/"
        install -m755 ${launcher} "$out/scripts/impeccable"

        # skills.sh installs skills, not provider-specific native agent registrations.
        # Keep isolated delegation by giving generic subagents self-contained briefs.
        cp -R "$out/reference/degraded" "$out/reference/agents"
        substituteInPlace "$out/reference/agents/"*.md --replace-fail \
          'This harness has no subagent capability, so you are running this role inline. Step fully out of the work you just finished, adopt only this file'"'"'s instructions for the pass, and disclose the substitution in one line when you report. Where the text below addresses a parent agent, you are both parties: produce the full output contract first, then act on it yourself.' \
          'Run this role in a fresh generic subagent. Follow the input and output contracts below and return the result to the parent.'
        substituteInPlace "$out/reference/new-work.md" \
          --replace-fail 'each spawn is the shipped asset producer with a single-comp packet' \
            'each spawn is a generic worker instructed to load reference/agents/asset-producer.md from this skill, with a single-comp packet' \
          --replace-fail 'spawn the shipped asset producer (`impeccable-asset-producer`; `impeccable_asset_producer` in codex; `/impeccable-asset-producer` in Cursor; on GitHub Copilot say "Use the impeccable-asset-producer agent")' \
            'spawn a generic worker instructed to load reference/agents/asset-producer.md from this skill' \
          --replace-fail 'Then spawn the shipped finish reviewer, `impeccable-finish-reviewer` (`impeccable_finish_reviewer` in codex; `/impeccable-finish-reviewer` in Cursor; on GitHub Copilot say "Use the impeccable-finish-reviewer agent"),' \
            'Then spawn a fresh generic reviewer instructed to load reference/agents/finish-reviewer.md from this skill,' \
          --replace-fail 'Never read the shipped agents'"'"' definition files before spawning; the harness loads them at spawn, and you owe only the input packet.' \
            'Pass the absolute role-brief path in the input packet without reading it in the parent; the generic subagent reads it before starting.' \
          --replace-fail 'spawn the shipped documenter, `impeccable-documenter` (`impeccable_documenter` in codex),' \
            'spawn a generic worker instructed to load reference/agents/documenter.md from this skill,'
        substituteInPlace "$out/reference/live.md" --replace-fail \
          'delegate source edits to `impeccable_manual_edit_applier` / `impeccable-manual-edit-applier`.' \
          'delegate source edits to a generic worker instructed to load reference/agents/manual-edit-applier.md from this skill.'

        export HOME="$TMPDIR/home"
        mkdir -p "$HOME"
        test "$("$out/scripts/impeccable" engine-probe)" = "impeccable-engine ${engineVersion}"
        "$out/scripts/impeccable" detect --list-rules > /dev/null
      '';
  url = "https://github.com/pbakaus/impeccable/releases/tag/skill-v${version}";
  skill = "impeccable";
}
