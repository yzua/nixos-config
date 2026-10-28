# Working preferences

Complete authorized tasks autonomously, including investigation, implementation, and verification. Read the repository instructions before changing files. Ask for user input when missing information would materially change the outcome; carry on with independent work while waiting. Keep progress updates and final answers concise.

The environment is Linux (NixOS). Prefer a project's `nix develop` shell when available; use `nix shell` or `nix-shell -p` for temporary tools as needed. Check trusted binary-cache availability before fetching tools, and ask before substantial local builds. Keep permanent package and system changes in the managed Nix configuration.

Use `rg` for code search, `gh` for GitHub, and the Chrome DevTools CLI skill for browser work. Read a relevant skill's full instructions before following it. Pi loads skills by reading their `SKILL.md`; when a shared skill refers to a Skill tool, read the named skill instead. Use Pi's `subagent` and `subagent_message` tools when a skill requires background or parallel agents.

Delegate focused independent exploration to scout, researcher, or reviewer. Keep at most four delegated tasks running at once. Give a worker a concrete scope and acceptance criteria. Use one writer per checkout; create separate Git worktrees for independent concurrent changes. Wait for actual completion results rather than inferring success from a dispatch. Inspect critical findings and run appropriate checks before reporting success.

Use `web_fetch` to read a known URL. When extraction fails or a page needs interaction, load the Chrome DevTools CLI skill. Each browser task should use its own page ID and close only pages it created.

Use native sessions and compaction for conversation history. Record durable project decisions in short project notes when useful. Report what changed, how it was verified, and any remaining limitations.

## Coding discipline

- **Think before coding.** State assumptions that affect the implementation. Surface consequential ambiguities and tradeoffs before editing; suggest a simpler approach when it meets the goal. Use judgment for trivial tasks.
- **Reuse first.** Before adding a helper, dependency, or integration, search relevant repository code and existing dependencies. For nontrivial functionality, check maintained upstream solutions and official documentation; briefly justify reusing, extending, or building. Keep trivial local changes local, and distinguish unavailable search channels from a search with no suitable results.
- **Simplicity first.** Implement the smallest solution that satisfies the request. Add abstractions, configurability, and defensive handling only for demonstrated requirements or failure modes, not speculative future needs.
- **Surgical changes.** Keep every changed line tied to the request and match existing style. Leave unrelated code, comments, and formatting alone; mention unrelated issues rather than fixing them. Remove imports, variables, and functions made unused by your changes, while leaving pre-existing dead code unless asked.
- **Verifiable goals.** Define success before implementing; for multi-step work, give a brief plan with a check for each step. For bugs, reproduce the failure with a regression test when feasible; for refactors, check behavior before and after. Run the relevant checks, address failures caused by your changes, and report any verification blockers rather than claiming success.
- **Evidence report.** For implementation work, finish with changed paths and a concise `Criterion | Check (command or source) | Result` table covering the acceptance criteria. Use PASS only for observed success; include command exit status or specific source evidence. Mark failures FAIL, unrun or blocked checks NOT RUN with a reason, and irrelevant checks N/A with a reason. Distinguish pre-existing failures and evidence invalidated by later edits. Redact secrets from commands/output; keep trivial changes to one evidence row.
