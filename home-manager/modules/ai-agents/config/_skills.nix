# Skill installations for all AI agents.
# Imported by config/defaults.nix.

{
  skills = [
    # Real tools — browser, device, and web app testing
    {
      repo = "vercel-labs/agent-browser";
      skill = "agent-browser";
    }
    {
      repo = "callstackincubator/agent-device";
      skill = "agent-device";
    }
    {
      repo = "anthropics/skills";
      skill = "webapp-testing";
    }

    # Methodology — Matt Pocock's engineering skills
    {
      repo = "mattpocock/skills";
      skill = "diagnose";
    }
    {
      repo = "mattpocock/skills";
      skill = "tdd";
    }
    {
      repo = "mattpocock/skills";
      skill = "grill-with-docs";
    }
    {
      repo = "mattpocock/skills";
      skill = "grill-me";
    }
    {
      repo = "mattpocock/skills";
      skill = "to-prd";
    }
    {
      repo = "mattpocock/skills";
      skill = "to-issues";
    }
    {
      repo = "mattpocock/skills";
      skill = "triage";
    }
    {
      repo = "mattpocock/skills";
      skill = "zoom-out";
    }
    {
      repo = "mattpocock/skills";
      skill = "improve-codebase-architecture";
    }
    {
      repo = "mattpocock/skills";
      skill = "caveman";
    }

    # Domain rules
    {
      repo = "vercel-labs/agent-skills";
      skill = "vercel-react-best-practices";
    }
    {
      repo = "vercel-labs/skills";
      skill = "find-skills";
    }
    {
      repo = "vercel-labs/agent-skills";
      skill = "web-design-guidelines";
    }
    {
      repo = "anthropics/skills";
      skill = "frontend-design";
    }

    # Browser testing
    {
      repo = "microsoft/playwright-cli";
      skill = "playwright-cli";
    }

    # Coding methodology — multi-agent analysis
    {
      repo = "michaelboeding/skills";
      skill = "debug-council";
    }
    {
      repo = "michaelboeding/skills";
      skill = "parallel-builder";
    }

    # Practical dev tools
    {
      repo = "mxyhi/ok-skills";
      skill = "gh-fix-ci";
    }
    {
      repo = "mxyhi/ok-skills";
      skill = "find-docs";
    }

    # Security
    {
      repo = "TerminalSkills/skills";
      skill = "security-audit";
    }

    # Reverse engineering
    {
      repo = "wshobson/agents";
      skill = "protocol-reverse-engineering";
    }

    # Documentation discipline
    {
      repo = "github/awesome-copilot";
      skill = "documentation-writer";
    }
    {
      repo = "addyosmani/agent-skills";
      skill = "documentation-and-adrs";
    }
  ];
}
