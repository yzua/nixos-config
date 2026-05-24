# Single source of truth for all agent aliases and workflow specs.
# Generates both Nix zsh aliases and a bash registry fragment
# sourced by scripts/ai/_agent-registry.sh at runtime.

{
  lib,
  pkgs,
  scriptsDir,
  ...
}:

let
  models = import ./_models.nix;
  workflowPrompts = import ./_workflow-prompts.nix { };
  commitSplitPrompt = workflowPrompts.commitSplit;
  refactorMaintainabilityPrompt = workflowPrompts.refactorMaintainability;
  securityAuditPrompt = workflowPrompts.securityAudit;
  bugfixRootCausePrompt = workflowPrompts.bugfixRootCause;
  dependencyUpgradePrompt = workflowPrompts.dependencyUpgrade;
  buildPerformancePrompt = workflowPrompts.buildPerformance;
  runtimePerformancePrompt = workflowPrompts.runtimePerformance;
  markdownSyncPrompt = workflowPrompts.markdownSync;

  codexBase = "command codex --no-alt-screen --dangerously-bypass-approvals-and-sandbox";
  codexHeadless = "codex exec --dangerously-bypass-approvals-and-sandbox";

  gptLowModel = models.gpt-low;
  gptMedModel = models.gpt-default;
  gptXHighModel = models.gpt-xhigh;

  mkAliasAttrs =
    aliasSpecs:
    builtins.listToAttrs (
      map (spec: {
        name = spec.alias;
        value = spec.command;
      }) aliasSpecs
    );

  # Single source of truth for all agent aliases.
  # Fields used by Nix zsh alias generation: alias, command, workflowPromptMode
  # Fields used by bash registry generation: envMarker, interactiveCommand, headlessCommand, tool, launcherSimple
  aiAgentAliasSpecs = [
    # Claude Code
    {
      alias = "cl";
      command = "claude";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = "claude --dangerously-skip-permissions";
      headlessCommand = "claude --print";
      tool = "claude";
      launcherSimple = true;
    }
    {
      alias = "clu";
      command = "claude --dangerously-skip-permissions";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = "claude --dangerously-skip-permissions";
      headlessCommand = "claude --dangerously-skip-permissions --print";
      tool = "claude";
      launcherSimple = false;
    }
    {
      alias = "ocl";
      command = "claude --model opus";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = "claude --dangerously-skip-permissions --model opus";
      headlessCommand = "claude --model opus --print";
      tool = "claude";
      launcherSimple = true;
    }
    {
      alias = "hcl";
      command = "claude --model haiku";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = "claude --dangerously-skip-permissions --model haiku";
      headlessCommand = "claude --model haiku --print";
      tool = "claude";
      launcherSimple = true;
    }
    {
      alias = "clglm";
      command = "claude_glm";
      workflowPromptMode = "positional";
      envMarker = "ZAI";
      interactiveCommand = "claude --dangerously-skip-permissions";
      headlessCommand = "claude --dangerously-skip-permissions --print";
      tool = "claude";
      launcherSimple = true;
    }

    # Codex
    {
      alias = "cx";
      command = codexBase;
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = "codex --no-alt-screen --dangerously-bypass-approvals-and-sandbox";
      headlessCommand = codexHeadless;
      tool = "codex";
      launcherSimple = true;
    }
    {
      alias = "lcx";
      command = "${codexBase} -c 'model_reasoning_effort=\"low\"'";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = ''codex --no-alt-screen --dangerously-bypass-approvals-and-sandbox -c 'model_reasoning_effort="low"' '';
      headlessCommand = "${codexHeadless} -c 'model_reasoning_effort=\"low\"'";
      tool = "codex";
      launcherSimple = true;
    }
    {
      alias = "mcx";
      command = "${codexBase} -c 'model_reasoning_effort=\"medium\"'";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = ''codex --no-alt-screen --dangerously-bypass-approvals-and-sandbox -c 'model_reasoning_effort="medium"' '';
      headlessCommand = "${codexHeadless} -c 'model_reasoning_effort=\"medium\"'";
      tool = "codex";
      launcherSimple = true;
    }
    {
      alias = "hcx";
      command = "${codexBase} -c 'model_reasoning_effort=\"high\"'";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = ''codex --no-alt-screen --dangerously-bypass-approvals-and-sandbox -c 'model_reasoning_effort="high"' '';
      headlessCommand = "${codexHeadless} -c 'model_reasoning_effort=\"high\"'";
      tool = "codex";
      launcherSimple = true;
    }
    {
      alias = "xcx";
      command = "${codexBase} -c 'model_reasoning_effort=\"xhigh\"'";
      workflowPromptMode = "positional";
      envMarker = "-";
      interactiveCommand = ''codex --no-alt-screen --dangerously-bypass-approvals-and-sandbox -c 'model_reasoning_effort="xhigh"' '';
      headlessCommand = "${codexHeadless} -c 'model_reasoning_effort=\"xhigh\"'";
      tool = "codex";
      launcherSimple = true;
    }

    # OpenCode (default and profiles)
    {
      alias = "oc";
      command = "opencode --log-level WARN";
      workflowPromptMode = "flag";
      envMarker = "-";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }
    {
      alias = "ocor";
      command = "opencode_openrouter";
      workflowPromptMode = "flag";
      envMarker = "OPENROUTER";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }
    {
      alias = "ocglm";
      command = "opencode_glm";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-glm";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }
    {
      alias = "ocgem";
      command = "opencode_gemini";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-gemini";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }
    {
      alias = "ocgpt";
      command = "opencode_gpt";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-gpt";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }
    {
      alias = "locgpt";
      command = "opencode_gpt --model ${gptLowModel}";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-gpt";
      interactiveCommand = "opencode --model ${gptLowModel}";
      headlessCommand = "opencode run --model ${gptLowModel}";
      tool = "opencode";
      launcherSimple = false;
    }
    {
      alias = "mocgpt";
      command = "opencode_gpt --model ${gptMedModel}";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-gpt";
      interactiveCommand = "opencode --model ${gptMedModel}";
      headlessCommand = "opencode run --model ${gptMedModel}";
      tool = "opencode";
      launcherSimple = false;
    }
    {
      alias = "xocgpt";
      command = "opencode_gpt --model ${gptXHighModel}";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-gpt";
      interactiveCommand = "opencode --model ${gptXHighModel}";
      headlessCommand = "opencode run --model ${gptXHighModel}";
      tool = "opencode";
      launcherSimple = false;
    }
    {
      alias = "ocs";
      command = "opencode_sonnet";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-sonnet";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }
    {
      alias = "oczen";
      command = "opencode_zen";
      workflowPromptMode = "flag";
      envMarker = "OPENCODE_CONFIG_DIR=$HOME/.config/opencode-zen";
      interactiveCommand = "opencode";
      headlessCommand = "opencode run";
      tool = "opencode";
      launcherSimple = true;
    }

    # Antigravity CLI
    {
      alias = "ag";
      command = "agy --dangerously-skip-permissions";
      workflowPromptMode = "flag";
      envMarker = "-";
      interactiveCommand = "agy --dangerously-skip-permissions";
      headlessCommand = "agy --dangerously-skip-permissions --prompt";
      tool = "antigravity";
      launcherSimple = true;
    }
    {
      alias = "gem";
      command = "agy --dangerously-skip-permissions";
      workflowPromptMode = "flag";
      envMarker = "-";
      interactiveCommand = "agy --dangerously-skip-permissions";
      headlessCommand = "agy --dangerously-skip-permissions --prompt";
      tool = "antigravity";
      launcherSimple = false;
    }

    # oh-my-pi
    {
      alias = "opi";
      command = "omp_glm";
      workflowPromptMode = "flag";
      envMarker = "ZAI_OMP";
      interactiveCommand = "omp";
      headlessCommand = "omp --prompt";
      tool = "omp";
      launcherSimple = false;
    }
  ];

  # Workflow prompt specs with labels for bash WORKFLOW_MAP generation.
  workflowPromptSpecs = [
    {
      suffix = "cm";
      prompt = commitSplitPrompt;
      envVar = "COMMIT_SPLIT_PROMPT";
      label = "commit split (cm) — Splits working tree into logical commits with validated, minimal staging.";
    }
    {
      suffix = "rf";
      prompt = refactorMaintainabilityPrompt;
      envVar = "REFACTOR_MAINTAINABILITY_PROMPT";
      label = "refactor maintainability (rf) — Improves structure and clarity without changing behavior, APIs, or workflows.";
    }
    {
      suffix = "fx";
      prompt = bugfixRootCausePrompt;
      envVar = "BUGFIX_ROOT_CAUSE_PROMPT";
      label = "bugfix root cause (fx) — Reproduces bugs, proves root cause, fixes minimally, validates regressions afterward.";
    }
    {
      suffix = "sa";
      prompt = securityAuditPrompt;
      envVar = "SECURITY_AUDIT_PROMPT";
      label = "security audit (sa) — Finds evidence-backed security weaknesses across code, configs, dependencies, infrastructure surfaces.";
    }
    {
      suffix = "du";
      prompt = dependencyUpgradePrompt;
      envVar = "DEPENDENCY_UPGRADE_PROMPT";
      label = "dependency upgrade (du) — Upgrades dependencies safely, handles breaking changes, validates compatibility, reports blockers.";
    }
    {
      suffix = "bp";
      prompt = buildPerformancePrompt;
      envVar = "BUILD_PERFORMANCE_PROMPT";
      label = "build performance (bp) — Measures bottlenecks, applies low-risk optimizations, compares before-and-after performance evidence clearly.";
    }
    {
      suffix = "rp";
      prompt = runtimePerformancePrompt;
      envVar = "RUNTIME_PERFORMANCE_PROMPT";
      label = "runtime performance (rp) — Measures real code-path bottlenecks, applies low-risk optimizations, and verifies before-and-after latency, throughput, or memory gains.";
    }
    {
      suffix = "md";
      prompt = markdownSyncPrompt;
      envVar = "MARKDOWN_SYNC_PROMPT";
      label = "markdown sync (md) — Synchronizes documentation with repository reality, removing drift, ambiguity, stale instructions.";
    }
  ];

  workflowAgentSpecs = builtins.filter (agent: agent ? workflowPromptMode) aiAgentAliasSpecs;

  aiWorkflowAliasSpecs = lib.flatten (
    map (
      workflow:
      map (agent: {
        alias = "${agent.alias}${workflow.suffix}";
        command =
          if agent.workflowPromptMode == "flag" then
            "_ai_agent_exec ${agent.alias}${workflow.suffix} -- ${agent.command} --prompt ${lib.escapeShellArg workflow.prompt}"
          else
            "_ai_agent_exec ${agent.alias}${workflow.suffix} -- ${agent.command} ${lib.escapeShellArg workflow.prompt}";
      }) workflowAgentSpecs
    ) workflowPromptSpecs
  );

  workflowClipboardAliasSpecs = map (workflow: {
    alias = "cp${workflow.suffix}";
    command =
      "if command -v wl-copy >/dev/null 2>&1; then printf '%s' ${lib.escapeShellArg workflow.prompt} | wl-copy; "
      + "elif command -v xclip >/dev/null 2>&1; then printf '%s' ${lib.escapeShellArg workflow.prompt} | xclip -selection clipboard; "
      + "else echo 'Clipboard tool not found (need wl-copy or xclip)' >&2; false; fi "
      + "&& echo 'Copied ${workflow.suffix} prompt to clipboard'";
  }) workflowPromptSpecs;

  aiAliases = mkAliasAttrs (
    (map (
      spec: spec // { command = "_ai_agent_exec ${spec.alias} -- ${spec.command}"; }
    ) aiAgentAliasSpecs)
    ++ aiWorkflowAliasSpecs
    ++ workflowClipboardAliasSpecs
  );

  mkWorkflowEnvVars =
    targetScript:
    let
      envAssignments = map (spec: "${spec.envVar}=${lib.escapeShellArg spec.prompt}") workflowPromptSpecs;
    in
    ''
      ${builtins.concatStringsSep " \\\n    " envAssignments} \
      exec ${targetScript} "$@"
    '';

  aiAgentLauncher = pkgs.writeShellScriptBin "ai-agent-launcher" (
    mkWorkflowEnvVars "${scriptsDir}/ai/agent-launcher.sh"
  );

  # --- Bash registry generation ---

  escapeForBashDoubleQuote = s: builtins.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ] s;

  # Whether an env marker contains shell variables that need expansion at source time.
  envMarkerNeedsQuoting = marker: builtins.match ".*\\$.*" marker != null;

  mkRegistryLine =
    spec:
    let
      envPart =
        if spec.envMarker == "-" then
          "-"
        else if envMarkerNeedsQuoting spec.envMarker then
          "\"${spec.envMarker}\""
        else
          spec.envMarker;
      interactivePart = "\"${escapeForBashDoubleQuote spec.interactiveCommand}\"";
      headlessPart = "\"${escapeForBashDoubleQuote spec.headlessCommand}\"";
    in
    "_def ${spec.alias}    ${envPart}    ${interactivePart}    ${headlessPart}";

  tools = lib.unique (map (spec: spec.tool) aiAgentAliasSpecs);
  simpleAliases = map (spec: spec.alias) (lib.filter (spec: spec.launcherSimple) aiAgentAliasSpecs);
  defLines = map mkRegistryLine aiAgentAliasSpecs;
  workflowSuffixes = map (spec: spec.suffix) workflowPromptSpecs;

  workflowMapEntries = map (
    spec: "  [${spec.suffix}]=\"${spec.label}|${spec.envVar}\""
  ) workflowPromptSpecs;

  aliasToolEntries = map (spec: "  [${spec.alias}]=\"${spec.tool}\"") aiAgentAliasSpecs;

  # Human-readable provider labels for the launcher's sectioned mode.
  providerLabels = {
    claude = "Claude Code";
    opencode = "OpenCode";
    codex = "Codex";
    antigravity = "Antigravity";
    omp = "oh-my-pi";
  };
  providerLabelEntries = lib.mapAttrsToList (tool: label: "  [${tool}]=\"${label}\"") providerLabels;
  # Sort providers by their display order in the launcher
  providerOrder = [
    "opencode"
    "claude"
    "codex"
    "antigravity"
  ];

  generatedBashRegistry = builtins.concatStringsSep "\n" (
    [
      "# Auto-generated alias registry — do not edit."
      "# Regenerate with: just home"
      "# Source: home-manager/modules/ai-agents/helpers/_aliases.nix"
      ""
      "# --- Agent registries (populated via _def from _agent-registry.sh) ---"
    ]
    ++ defLines
    ++ [
      ""
      "# --- Supported tools ---"
      "SUPPORTED_TOOLS=(${builtins.concatStringsSep " " tools})"
      ""
      "# --- Simple aliases for launcher quick-pick ---"
      "LAUNCHER_SIMPLE_ALIASES=(${builtins.concatStringsSep " " simpleAliases})"
      ""
      "# --- Alias -> tool mapping ---"
      "declare -A ALIAS_TOOLS=("
    ]
    ++ aliasToolEntries
    ++ [
      ")"
      ""
      "# --- Provider display labels and order ---"
      "PROVIDER_ORDER=(${builtins.concatStringsSep " " providerOrder})"
      "declare -A PROVIDER_LABELS=("
    ]
    ++ providerLabelEntries
    ++ [
      ")"
      ""
      "# --- Workflow suffixes ---"
      "WORKFLOW_SUFFIXES=(${builtins.concatStringsSep " " workflowSuffixes})"
      ""
      "# --- Workflow metadata: suffix -> \"label|env_var\" ---"
      "declare -A WORKFLOW_MAP=("
    ]
    ++ workflowMapEntries
    ++ [ ")" ]
  );
in
{
  inherit
    aiAliases
    aiAgentLauncher
    generatedBashRegistry
    workflowPrompts
    mkWorkflowEnvVars
    ;
  aiAgentInventory = pkgs.writeShellScriptBin "ai-agent-inventory" ''
    exec ${scriptsDir}/ai/agent-inventory.sh "$@"
  '';
}
