

# NixOS System Configuration

Flake-based NixOS + Home Manager config with Niri compositor, Noctalia Shell, GruvboxAlt theming, and full privacy/monitoring stack.

---

## Quick Start

```bash
git clone <repo-url> ~/System
cd ~/System
```

Edit `shared/constants.nix` for your identity (the `user.handle` field drives the flake's `user` variable).

Create your host:

```bash
cp -r hosts/desktop hosts/<your-hostname>
cp /etc/nixos/hardware-configuration.nix hosts/<your-hostname>/
```

Register in `hosts/_inventory.nix`:

```nix
[
  { hostname = "desktop"; stateVersion = "26.05"; enabled = true; }
  { hostname = "your-hostname"; stateVersion = "26.05"; enabled = true; }
]
```

Deploy the current personal desktop config:

```bash
just all   # hardcoded to desktop: modules, pkgs, lint -> format -> test -> check -> nixos -> home
```

For a newly added host, use explicit `nh` commands instead of the hardcoded `just home` / `just nixos` recipes.

---

## Commands

| Command                   | Description                                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `just all`                | Full desktop pipeline: `modules`, `pkgs`, `lint` in parallel; then `format -> test -> check -> nixos -> home` |
| `just home`               | Apply Home Manager for `yz@desktop`                                                                           |
| `just nixos`              | Apply NixOS for `desktop`                                                                                     |
| `just modules`            | Validate import structure                                                                                     |
| `just pkgs`               | Check for duplicate packages and program/module ownership conflicts                                           |
| `just lint`               | statix + deadnix + shellcheck + inline Nix shell scripts + markdownlint                                       |
| `just dead`               | deadnix only (subset of lint)                                                                                 |
| `just test`               | Run all shell test suites                                                                                     |
| `just format`             | `nix fmt` (nixfmt-tree via flake formatter)                                                                   |
| `just check`              | `nix flake check --no-build path:.`                                                                           |
| `just diff`               | Diff current vs previous NixOS generation                                                                     |
| `just report [mode]`      | Generate system health report                                                                                 |
| `just report-view [type]` | View latest system report                                                                                     |
| `just update`             | Update flake inputs (pre/post health checks)                                                                  |
| `just upgrade`            | Full upgrade: update → nixos → home → security-audit                                                          |
| `just clean`              | `nh clean all --keep 1` + HM generation expiry + store optimise                                               |
| `just install-hooks`      | Install repo-local pre-commit/pre-push hooks                                                                  |
| `just sops-edit`          | Edit encrypted secrets                                                                                        |
| `just sops-view`          | View secrets (read-only)                                                                                      |
| `just secrets-add KEY`    | Add a single secret (prompted securely)                                                                       |
| `just security-audit`     | Systemd hardening + CVE scan                                                                                  |

---

## System Options (`mySystem.*`)

Set `hostProfile` first, then override as needed:

| Option                       | Description                                                               |
| ---------------------------- | ------------------------------------------------------------------------- |
| `hostProfile`                | `"desktop"` or `"laptop"` — sets defaults below                           |
| `nvidia.enable`              | NVIDIA drivers, CUDA, Wayland                                             |
| `fwupd.enable`               | Firmware updates (LVFS)                                                   |
| `gaming.enable`              | Steam, Lutris, Wine, MangoHud                                             |
| `gaming.enableGamemode`      | Feral GameMode daemon                                                     |
| `gaming.enableGamescope`     | Gamescope compositor                                                      |
| `bluetooth.enable`           | Bluetooth services                                                        |
| `bluetooth.powerOnBoot`      | Auto-power Bluetooth adapter on boot                                      |
| `mullvadVpn.enable`          | Mullvad VPN                                                               |
| `tor.enable`                 | Tor SOCKS proxy (port 9050)                                               |
| `i2pd.enable`                | I2P anonymous network router                                              |
| `i2pd.port`                  | I2P transport port (used with firewall opening)                           |
| `i2pd.openFirewall`          | Open firewall for I2P transport port                                      |
| `i2pd.notransit`             | Disable transit tunnel participation                                      |
| `i2pd.bandwidth`             | Optional I2P bandwidth cap (KB/s)                                         |
| `yggdrasil.enable`           | Yggdrasil mesh network                                                    |
| `dnscryptProxy.enable`       | Encrypted DNS with DNSSEC                                                 |
| `docker.enable`              | Docker container engine with bridge networking                            |
| `libvirt.enable`             | libvirt/QEMU virtual machine management                                   |
| `flatpak.enable`             | Flatpak + Flathub                                                         |
| `printing.enable`            | CUPS                                                                      |
| `nautilus.enable`            | GNOME Files                                                               |
| `nixLd.enable`               | Dynamic linker for non-Nix binaries                                       |
| `cleanup.enable`             | Automated cleanup timers                                                  |
| `backup.enable`              | Restic backups (requires sops secret)                                     |
| `backup.repository`          | Restic repository target path                                             |
| `netdata.enable`             | System monitoring (port 19999)                                            |
| `scrutiny.enable`            | Disk health (port 8080)                                                   |
| `glance.enable`              | Dashboard (port 8082)                                                     |
| `opensnitch.enable`          | Application firewall                                                      |
| `ntfy.enable`                | Alertmanager → ntfy.sh notifications                                      |
| `firewall.enable`            | Network firewall and hostname leak prevention                             |
| `opsec.enable`               | Session lock, zram swap, Chrony NTS                                       |
| `securityServices.enable`    | dbus-broker and journald hardening                                        |
| `ntfy.port`                  | Local ntfy bridge listener port                                           |
| `observability.enable`       | Prometheus + Alertmanager + Grafana (ports 9090, 9093, 3001)              |
| `loki.enable`                | Log aggregation with Grafana Alloy                                        |
| `alloy.enable`               | Grafana Alloy log shipper for Loki (on by default)                        |
| `systemReport.enable`        | Unified health reporting                                                  |
| `systemReport.outputDir`     | System report output directory                                            |
| `systemReport.retentionDays` | System report retention window (days)                                     |
| `greetd.enable`              | Display manager                                                           |
| `waydroid.enable`            | Android emulation                                                         |
| `fail2ban.enable`            | fail2ban intrusion prevention                                             |
| `aide.enable`                | AIDE file integrity monitoring (default: on)                              |
| `metadataScrubber.enable`    | System-side metadata scrubber tooling (`mat2`/`exiftool`/`inotify-tools`) |
| `monitoring.enable`          | System monitoring tools (iotop, sysstat, sensors, vnStat, bandwhich)      |
| `lynis.enable`               | Weekly Lynis security audit                                               |
| `kdeconnect.enable`          | KDE Connect phone integration                                             |
| `vnc.enable`                 | VNC remote access                                                         |
| `secureBoot.enable`          | Secure Boot preparation with sbctl                                        |
| `webRe.enable`               | Web reverse engineering and security tools (on by default)                |
| `android.enable`             | ADB, Fastboot, Android Studio (on by default)                             |
| `browserDeps.enable`         | Chromium, Puppeteer headless testing dependencies (on by default)         |

---

## Security

Always-on: kernel hardening, AppArmor, hidepid=2, coredump suppression.

On by default (toggleable): AIDE file integrity, fail2ban, Lynis weekly audit, metadata scrubber (`mat2`/`exiftool`/`inotify-tools`), Mullvad VPN, Tor, DNSCrypt, OpenSnitch, Secure Boot, Waydroid, web RE/security tools, firewall (hostname leak prevention), zram swap, Chrony NTS, journald hardening, dbus-broker.

Profile-dependent defaults: gaming/gamemode/gamescope (on for `desktop`), bluetooth (on for `laptop`).

Off by default (toggleable): Yggdrasil, I2P, backup (requires sops secret), VNC.

---

## Services

All local, no cloud. Toggle via `mySystem.*`:

### Monitoring & Observability

| Service      | Port  | Purpose                       |
| ------------ | ----- | ----------------------------- |
| Netdata      | 19999 | Real-time system metrics      |
| Scrutiny     | 8080  | SMART disk health             |
| Glance       | 8082  | Unified dashboard             |
| Grafana      | 3001  | Custom dashboards             |
| Prometheus   | 9090  | Metrics collection/alerting   |
| Alertmanager | 9093  | Alert routing                 |
| ntfy bridge  | 8090  | Push notifications to ntfy.sh |
| InfluxDB2    | 8086  | Scrutiny metrics backend      |

### Log Aggregation

| Service       | Port  | Purpose            |
| ------------- | ----- | ------------------ |
| Loki          | 3100  | Log storage (HTTP) |
| Loki          | 9096  | Log storage (gRPC) |
| Grafana Alloy | 12345 | Log collector      |

### Privacy & Network

| Service         | Port | Purpose                                                   |
| --------------- | ---- | --------------------------------------------------------- |
| Tor SOCKS       | 9050 | SOCKS proxy                                               |
| Tor DNS         | 9053 | DNS over Tor                                              |
| I2PD Webconsole | 7070 | I2P router web UI                                         |
| I2PD HTTP       | 4444 | I2P HTTP proxy (upstream default, not in `constants.nix`) |
| I2PD SOCKS      | 4447 | I2P SOCKS proxy                                           |
| I2PD Transport  | \*   | I2P transport (configurable)                              |
| Yggdrasil       | —    | Mesh network (outbound only)                              |

### System Services & Features

| Service/Feature                         | Toggle                       | Notes                                          |
| --------------------------------------- | ---------------------------- | ---------------------------------------------- |
| NVIDIA drivers + CUDA                   | `mySystem.nvidia.enable`     | Proprietary NVIDIA stack                       |
| Firmware updates (fwupd)                | `mySystem.fwupd.enable`      | LVFS firmware updates                          |
| Bluetooth + Blueman                     | `mySystem.bluetooth.enable`  | Desktop Bluetooth management                   |
| Flatpak + Flathub                       | `mySystem.flatpak.enable`    | Additional app ecosystem                       |
| CUPS printing                           | `mySystem.printing.enable`   | Local/network printer support                  |
| GNOME Files integration                 | `mySystem.nautilus.enable`   | File manager + thumbnailers                    |
| Dynamic linker for non-Nix binaries     | `mySystem.nixLd.enable`      | Compatibility for external binaries            |
| Docker container engine                 | `mySystem.docker.enable`     | Container runtime with bridge networking       |
| libvirt/QEMU                            | `mySystem.libvirt.enable`    | Virtual machine management                     |
| Waydroid                                | `mySystem.waydroid.enable`   | Android container runtime                      |
| greetd + tuigreet                       | `mySystem.greetd.enable`     | Display manager/login UI                       |
| OpenSnitch firewall                     | `mySystem.opensnitch.enable` | Outbound app firewalling                       |
| KDE Connect                             | `mySystem.kdeconnect.enable` | Phone integration                              |
| VNC stack (x11vnc + noVNC + websockify) | `mySystem.vnc.enable`        | Remote desktop (SSH-tunneled, ports 5900/6080) |
| Cleanup timers                          | `mySystem.cleanup.enable`    | Downloads/cache retention jobs                 |
| Restic backup jobs                      | `mySystem.backup.enable`     | Scheduled backups with pruning                 |
| fail2ban intrusion prevention           | `mySystem.fail2ban.enable`   | SSH/auth log monitoring                        |
| Secure Boot preparation                 | `mySystem.secureBoot.enable` | sbctl for Secure Boot setup                    |
| Web RE/security tools                   | `mySystem.webRe.enable`      | Nuclei, Nikto, SQLMap, Subfinder, WhatWeb      |

### User-level (Home Manager)

| Service       | Port | Purpose                                                         |
| ------------- | ---- | --------------------------------------------------------------- |
| ActivityWatch | 5600 | App usage tracking                                              |
| Syncthing     | 8384 | File synchronization (upstream default, not in `constants.nix`) |

---

## Structure

```
flake.nix                     # Entry point
flake.lock                    # Pinned input versions
justfile                      # Build/deploy commands (`just --list`)
AGENTS.md                     # Agent-facing repo conventions
LICENSE                       # Repository license
shared/                       # Shared identity and option utilities
hosts/<hostname>/             # Per-host config + hardware modules
nixos-modules/                # Shared system modules (58 imports in hub)
home-manager/                 # User-level modules + packages
scripts/                      # Utility scripts (ai/, build/, apps/, hardware/, system/, sops/; shared helpers in lib/)
secrets/secrets.yaml          # Encrypted secrets (sops-nix)
dev-shells/                   # Per-language dev shell templates (nix flake init -t <flake>#<template>; independent flakes)
guides/                       # User-facing tool guides (AI Agents, Ghostty, Niri, Neovim, Yazi, Zellij)
themes/                       # GruvboxAlt theme overrides (LibreWolf CSS, Telegram Desktop, YouTube Music)
```

Area-specific guidance in `AGENTS.md` files throughout the repo.

---

## Secrets

```bash
just sops-edit   # Edit (auto encrypt/decrypt)
just sops-view   # View (read-only)
```

Private key at `~/.config/sops/age/keys.txt`.
