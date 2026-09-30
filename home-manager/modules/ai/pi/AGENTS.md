# Working preferences

Complete authorized tasks autonomously, including investigation, implementation, and verification. Read the repository instructions before changing files. Ask for user input when missing information would materially change the outcome; carry on with independent work while waiting. Keep progress updates and final answers concise.

Use `rg` for code search, `gh` for GitHub, and the Chrome DevTools CLI skill for browser work. Read a relevant skill's full instructions before following it. Pi loads skills by reading their `SKILL.md`; when a shared skill refers to a Skill tool, read the named skill instead. Use Pi's `subagent` and `subagent_message` tools when a skill requires background or parallel agents.

Delegate focused independent exploration to scout, researcher, or reviewer. Keep at most two delegated tasks running at once. Give a worker a concrete scope and acceptance criteria. Use one writer per checkout; create separate Git worktrees for independent concurrent changes. Wait for actual completion results rather than inferring success from a dispatch. Inspect critical findings and run appropriate checks before reporting success.

Use `web_fetch` to read a known URL. When extraction fails or a page needs interaction, load the Chrome DevTools CLI skill. Each browser task should use its own page ID and close only pages it created.

Use native sessions and compaction for conversation history. Record durable project decisions in short project notes when useful. Report what changed, how it was verified, and any remaining limitations.
