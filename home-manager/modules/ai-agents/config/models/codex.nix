# Codex CLI configuration: model, profiles, custom agents, and developer instructions.

{
  config,
  ...
}:

{
  programs.aiAgents.codex = {
    enable = true;
    # Bare model name required — ChatGPT OAuth rejects the "openai/" provider prefix.
    model = "gpt-5.5";
    sandboxMode = "danger-full-access";
    enableSearch = false;
    personality = "pragmatic";
    reasoningEffort = "medium";
    approvalPolicy = "never";
    features = {
      apps = false;
      child_agents_md = true;
      hooks = true;
      multi_agent = true;
      plugins = true;
      shell_snapshot = true;
      tool_suggest = true;
      unified_exec = true;
    };
    trustedProjects = [
      "${config.home.homeDirectory}/System"
    ];
    profiles = {
      quick = {
        reasoningEffort = "low";
        approvalPolicy = "never";
        sandboxMode = "danger-full-access";
      };
      deep = {
        reasoningEffort = "xhigh";
        approvalPolicy = "never";
        sandboxMode = "danger-full-access";
      };
      safe = {
        approvalPolicy = "never";
        sandboxMode = "danger-full-access";
      };
      review = {
        personality = "pragmatic";
        reasoningEffort = "high";
        approvalPolicy = "never";
        sandboxMode = "danger-full-access";
        developerInstructions = ''
          Run in review mode. Prioritize bugs, regressions, security issues, and missing tests.
          Findings come first with exact file and line references when available.
        '';
      };
    };
    customAgents = {
      reviewer = {
        description = "Review-focused agent for bugs, regressions, security issues, and missing tests.";
        reasoningEffort = "high";
        approvalPolicy = "never";
        sandboxMode = "danger-full-access";
        developerInstructions = ''
          Perform code review only. Do not implement changes.
          Prioritize correctness, behavior drift, security issues, and test gaps.
          Findings must be concise, ordered by severity, and include exact evidence.
        '';
      };
      recon = {
        description = "Read-heavy reverse-engineering triage agent for static inspection and evidence gathering.";
        reasoningEffort = "high";
        approvalPolicy = "never";
        sandboxMode = "danger-full-access";
        enableSearch = true;
        developerInstructions = ''
          Focus on static triage and evidence gathering.
          Map strings, imports, symbols, embedded endpoints, protocols, config formats, and trust boundaries.
          Do not mutate files or run samples unless explicitly asked.
        '';
      };
    };
    extraToml = ''
      plan_mode_reasoning_effort = "high"
      web_search = "cached"
      model_verbosity = "low"

      [agents]
      max_threads = 6

      [agents.explorer]
      description = "Read-only style codebase exploration, file tracing, and evidence gathering."
      sandbox_mode = "danger-full-access"
      approval_policy = "never"
      model_reasoning_effort = "medium"

      [agents.worker]
      description = "Targeted implementation and fixes after the task is understood."
      sandbox_mode = "danger-full-access"
      approval_policy = "never"
      model_reasoning_effort = "medium"

      [agents.monitor]
      description = "Long-running command, build, and polling monitor with concise status updates."
      sandbox_mode = "danger-full-access"
      approval_policy = "never"
      model_reasoning_effort = "low"
    '';
  };
}
