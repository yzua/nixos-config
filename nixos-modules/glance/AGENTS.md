# Glance Dashboard

Self-hosted dashboard at `localhost:8082` with Gruvbox theme. Aggregates feeds, service health, Docker containers, and system stats.

**Option**: `mySystem.glance.enable` (default: `true` in host-defaults.nix)

---

## Structure

| File                        | Purpose                                                  |
| --------------------------- | -------------------------------------------------------- |
| `default.nix`               | Main module option and service wiring                    |
| `_settings.nix`             | Dashboard settings tree + all widget data (consolidated) |
| `_github-token-service.nix` | systemd token bootstrap for authenticated GitHub widgets |
| `_service-sites.nix`        | Health check endpoints (Netdata, Grafana, etc.)          |
| `_color-helpers.nix`        | Hex→HSL color conversion for Gruvbox theming             |

Helper files (prefixed `_`) are imported via `import ./_file.nix` — not listed in any `default.nix`.

All widget data (bookmarks, search bangs, Reddit feeds, YouTube channels, GitHub repos, market symbols, server stats, trending/activity widgets) lives in `_settings.nix` as `let` bindings.

---

## Pages (4)

| Page        | Content                                                                                         |
| ----------- | ----------------------------------------------------------------------------------------------- |
| **Home**    | Markets widget + 3-column layout (search/services, HN/YouTube/Reddit, stats/bookmarks/releases) |
| **Search**  | Full-width search + bookmarks                                                                   |
| **YouTube** | Full-width YouTube subscriptions                                                                |
| **GitHub**  | Trending repos, notifications, personal repos, releases                                         |

---

## Adding a Widget

1. Edit `_settings.nix` → add data to a `let` binding, then reference in the page layout
2. Run: `just nixos`

## Adding a Health Check

1. Edit `_service-sites.nix`
2. Add `{ title = "Name"; url = constants.urls.X; }`
3. Run: `just nixos`

## GitHub Token

GitHub widgets (notifications, personal repos, authenticated releases) need a GitHub token. Extracted automatically from `gh auth token` at service start via `ExecStartPre` — no manual secret management needed.

Prerequisite: `gh auth login` must have been run as user `yz`. If not authenticated, GitHub widgets silently degrade (trending and unauthenticated widgets still work).
