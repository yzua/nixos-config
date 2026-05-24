{
  cfg,
  aiAliases,
  constants,
}:
let
  ol = "~/${constants.paths.opencodeLogDir}";
  cl = "~/${constants.paths.codexLogDir}";
  al = "~/${constants.paths.aiAgentsLogDir}";
in
(
  if cfg.logging.enable then
    {
      "cl-log" = "ai-agent-log-wrapper claude claude";
      "oc-log" = "ai-agent-log-wrapper opencode opencode";
      "oc-port" = "opencode --port 4096";
      "codex-log" = "ai-agent-log-wrapper codex codex";
      "ag-log" = "ai-agent-log-wrapper antigravity agy";
      "opi-log" = "ai-agent-log-wrapper omp omp";

      "ai-logs" = "tail -f ${al}/*.log ${ol}/*.log ${cl}/*.log 2>/dev/null";
      "ai-errors" = "ai-agent-analyze errors";
      "ai-errors-all" = "ai-agent-analyze patterns";
      "ai-errors-runtime" = "ai-agent-analyze errors";

      "ai-stats" = "ai-agent-analyze stats";
      "ai-report" = "ai-agent-analyze report";
      "ai-dash" = "ai-agent-dashboard";
      "ais" = "ai-agent-launcher";
      "ait" = "ai-agent-inventory";
    }
  else
    { }
)
// (
  if cfg.herdr.enable then
    {
      hd = "herdr";
      hds = "herdr status";
      hdstop = "herdr server stop";
      hdi = "herdr integration status";
      hdagents = "herdr agent list";
      hdlogs = "tail -F ~/.config/herdr/herdr*.log 2>/dev/null";
    }
  else
    { }
)
// (
  if cfg.agentmemory.enable then
    {
      "mem-start" = "systemctl --user start agentmemory.service";
      "mem-stop" = "systemctl --user stop agentmemory.service";
      "mem-status" = "systemctl --user status agentmemory.service";
      "mem-health" = "curl -fsS ${cfg.agentmemory.url}/agentmemory/health";
      "mem-view" = "xdg-open ${cfg.agentmemory.viewerUrl}";
    }
  else
    { }
)
// aiAliases
// {
  "ai-mcp-scan" =
    "echo 'mcp-scan package is unavailable; running health checks instead' && ai-mcp-health";
  "ai-mcp-health" =
    "(command -v node >/dev/null && command -v bun >/dev/null && command -v bunx >/dev/null && command -v uvx >/dev/null && command -v github-mcp-server >/dev/null && command -v semgrep >/dev/null && gh auth status >/dev/null 2>&1 && [ -f ~/.mcp.json ] && jq -e . ~/.mcp.json >/dev/null && ! grep -q '__GITHUB_TOKEN_PLACEHOLDER__' ~/.mcp.json && echo 'MCP health: ok') || (echo 'MCP health: check failed' && false)";
}
