# Glance Dashboard

Self-hosted dashboard at `localhost:8082` with Gruvbox theme. Aggregates feeds, service health, Docker containers, and system stats.

**Option**: `mySystem.glance.enable` (default: `true` in host-defaults.nix)

---

## Structure

| File                          | Purpose                                                    |
| ----------------------------- | ---------------------------------------------------------- |
| `default.nix`                 | Main module option and service wiring                      |
| `_settings.nix`               | Glance dashboard settings tree                             |
| `_github-token-service.nix`   | systemd token bootstrap for authenticated GitHub widgets   |
| `_bookmarks.nix`              | Bookmark groups (AI, Dev, Social, Accounts)                |
| `_search-bangs.nix`           | DuckDuckGo bang shortcuts (!gh, !nix, !yt, !crate, !npm)   |
| `_service-sites.nix`          | Health check endpoints (Netdata, Grafana, etc.)            |
| `_youtube-channels.nix`       | YouTube subscriptions feed                                 |
| `_github-releases.nix`        | GitHub release tracker (rust, niri, neovim, glance)        |
| `_github-trending.nix`        | Trending repos widget (OSSInsight API, no auth)            |
| `_github-activity.nix`        | GitHub notifications + personal repos (needs GITHUB_TOKEN) |
| `_reddit.nix`                 | Reddit subreddit feeds (unixporn, nixos, linux)            |
| `_markets.nix`                | Market indices widget data                                 |
| `_color-helpers.nix`          | Shared color utility functions                             |
| `_server-stats.nix`           | Server stats widget (disk mountpoints)                     |

Helper files (prefixed `_`) are imported via `import ./_file.nix` — not listed in any `default.nix`.

---

## Pages (4)

| Page        | Content                                                                                         |
| ----------- | ----------------------------------------------------------------------------------------------- |
| **Home**    | Markets widget + 3-column layout (search/services, HN/YouTube/Reddit, stats/bookmarks/releases) |
| **Search**  | Full-width search + bookmarks                                                                   |
| **YouTube** | Full-width YouTube subscriptions                                                                |
| **GitHub**  | Trending repos, notifications, personal repos, releases                                         |

---

## Widgets

### Left Sidebar

- **Search**: DuckDuckGo with bang shortcuts
- **Monitor**: Service health checks (1m cache)
- **Docker Containers**: Running container list

### Center

- **Hacker News**: Top 10, sorted by engagement
- **Videos**: YouTube subscriptions (grid-cards style)
- **Reddit**: r/unixporn, r/nixos, r/linux (vertical-list style)

### Right Sidebar

- **Server Stats**: Local disk mountpoints (`/`, `/home`)
- **Bookmarks**: Grouped links
- **Releases**: GitHub release tracker (rust, niri, neovim, glance, authenticated)

### GitHub Page

- **Trending**: All-language daily trending repos (OSSInsight API)
- **Notifications**: Personal GitHub notifications (GITHUB_TOKEN)
- **My Repos**: Personal repos sorted by update (GITHUB_TOKEN)
- **Releases**: Same as Home sidebar

---

## Theming

Gruvbox dark theme applied via `theme` block. `branding.app-background-color` pulls from `constants.color.bg`.

---

## Adding a Widget

1. Edit `default.nix` → add widget to appropriate column
2. For external data (bookmarks, channels): create `_file.nix` helper, import at top
3. Run: `just nixos`

## Adding a Health Check

1. Edit `_service-sites.nix`
2. Add `{ title = "Name"; url = "http://host:port"; }`
3. Run: `just nixos`

## Adding a YouTube Channel

1. Edit `_youtube-channels.nix`
2. Add `{ id = "CHANNEL_ID"; name = "Display Name"; }`
3. Run: `just nixos`

## GitHub Token

GitHub widgets (notifications, personal repos, authenticated releases) need a GitHub token. Extracted automatically from `gh auth token` at service start via `ExecStartPre` — no manual secret management needed.

Prerequisite: `gh auth login` must have been run as user `yz`. If not authenticated, GitHub widgets silently degrade (trending and unauthenticated widgets still work).
