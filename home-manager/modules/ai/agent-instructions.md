# Working preferences

Complete authorized tasks autonomously, including investigation, implementation, and verification. Read repository instructions before changing files. Ask when missing information would materially change the outcome. Keep progress updates and final answers concise; report changed paths, verification, and remaining limitations.

The environment is Linux (NixOS). Prefer a project's `nix develop` shell when available; use `nix shell` or `nix-shell -p` for temporary tools as needed. Check trusted binary-cache availability before fetching tools, and ask before substantial local builds. Keep permanent package and system changes in the managed Nix configuration. Get approval before system or Home Manager activation and changes to credential storage; keep secrets out of Git and Nix store paths.

Use `gh` for GitHub. Read a relevant skill's full instructions before following it.

Use parallel agents for focused independent work when available, with at most two delegated tasks running at once. Keep one writer per checkout; use separate Git worktrees for independent concurrent changes. Wait for actual completion results, inspect critical findings, and run appropriate checks before reporting success. Preserve unrelated work.
