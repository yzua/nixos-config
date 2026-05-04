# Development tools, databases, and reverse engineering.

{ pkgs, pkgsStable, ... }:

let
  curlImpersonateNoWcurl = pkgs.symlinkJoin {
    name = "curl-impersonate-no-wcurl";
    paths = [ pkgs.curl-impersonate ];
    postBuild = ''
      rm -f "$out/bin/wcurl"
    '';
    inherit (pkgs.curl-impersonate) meta;
  };

  latest = with pkgs; [
    aider-chat # AI pair programming (fast-moving, needs latest)
    cargo
    cargo-nextest
    rustc
    rustfmt # Rust formatter (system-wide for conform.nvim)
    zig # Zig compiler + formatter (used by AI agent hooks and editors)
    clippy # Rust linter (system-wide for outside dev-shells)
    nixfmt # Nix formatter
    statix # Nix linter
    deadnix # Nix dead code detector
    nix-tree # Nix dependency explorer
    nix-output-monitor # Better Nix build output
    cachix # Binary cache client
    nix-init # Generate Nix packages from URLs
    nurl # Nix URL fetcher hash helper
    uv # Python package manager; provides uvx for MCP servers
    python313Packages.fastmcp # Pythonic MCP server/client framework
    docker-compose
    mdbook # Book generator from Markdown (Rust/Nix ecosystem standard)
    repomix # Bundle repo into single file for AI context windows
    sccache # Shared compilation cache (Rust/C++)
    process-compose # Multi-service dev orchestrator
    curlImpersonateNoWcurl # Browser-like TLS/HTTP2 fingerprints without wcurl collision
  ];

  stable = with pkgsStable; [
    # API development
    bruno
    burpsuite
    hurl
    httpie # HTTP request runner with assertions (CI-friendly API testing)
    grpcurl # CLI for gRPC services (reflection + file descriptor support)

    # Build tools
    act # Run GitHub Actions locally in Docker
    earthly # Reproducible CI builds (Dockerfile + Makefile hybrid)
    git-lfs
    just
    pandoc

    # C/C++ development
    cmake
    gcc
    gdb
    gnumake
    ltrace
    strace
    valgrind

    # Container tools
    dive # Container image layer analysis
    skopeo # Container image inspection and copy (no daemon needed)

    # Databases (postgresql provides psql client + libs for local dev)
    dbeaver-bin
    dolt # Version-controlled SQL database (Beads backend)
    pgcli # Auto-completing PostgreSQL CLI (drop-in psql replacement)
    litecli # Auto-completing SQLite CLI
    postgresql
    redis
    sqlite

    # Documentation
    d2 # Declarative diagramming language (text -> SVG)
    typst # Modern typesetting system (fast LaTeX alternative)

    # Java
    openjdk21

    # Linters
    hadolint # Dockerfile best practices linter
    shellcheck # Shell script static analysis (required by nvim-lint)

    # Profiling
    heaptrack # Heap memory profiler (allocation tracking + GUI)
    tokio-console # Real-time async Rust (tokio) diagnostics

    # Reverse engineering (android-tools provided by nixos-modules/android.nix)
    androguard
    apktool
    binwalk
    cutter
    frida-tools
    ghidra-bin
    jadx
    radare2
    scrcpy

    # Security and pattern analysis
    yara # Pattern matching engine for malware/rules detection
    hashid # Hash type identification from hash strings
    cewl # Custom wordlist generator by spidering target sites

    # Rust development
    bacon
    cargo-deny
    cargo-tarpaulin # Rust code coverage
    cargo-watch

    # C/C++ static analysis
    cppcheck

    # Shell scripting
    bats # Bash testing framework
    shfmt # Shell script formatter

  ];
in
{
  home.packages =
    latest
    ++ stable
    ++ [
      pkgs.apkid
      pkgs.objection
      pkgs.cyberchef
      pkgs.jwt-cli
      pkgs.rizin
      pkgs.step-cli
    ];
}
