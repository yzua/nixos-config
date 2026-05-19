# Glance dashboard settings tree.
#
# Widget data previously split across 9 separate files has been consolidated
# here for locality — the entire dashboard layout is visible in one file.
# Files containing logic (_color-helpers, _service-sites, _github-token-service)
# remain separate.

{ constants }:

let
  hexToGlanceHsl = import ./_color-helpers.nix;

  # --- Widget data ---

  searchBangs = [
    {
      title = "GitHub";
      shortcut = "!gh";
      url = "https://github.com/search?q={QUERY}";
    }
    {
      title = "NixOS";
      shortcut = "!nix";
      url = "https://search.nixos.org/packages?query={QUERY}";
    }
    {
      title = "YouTube";
      shortcut = "!yt";
      url = "https://www.youtube.com/results?search_query={QUERY}";
    }
    {
      title = "Crates";
      shortcut = "!crate";
      url = "https://crates.io/search?q={QUERY}";
    }
    {
      title = "NPM";
      shortcut = "!npm";
      url = "https://www.npmjs.com/search?q={QUERY}";
    }
  ];

  bookmarkGroups = [
    {
      title = "AI";
      links = [
        {
          title = "Claude";
          url = "https://claude.ai/";
          icon = "si:anthropic";
        }
        {
          title = "ChatGPT";
          url = "https://chatgpt.com/";
          icon = "si:openai";
        }
      ];
    }
    {
      title = "Dev";
      links = [
        {
          title = "GitHub";
          url = "https://github.com";
          icon = "si:github";
        }
        {
          title = "Excalidraw";
          url = "https://excalidraw.com/";
          icon = "si:excalidraw";
        }
        {
          title = "Codeberg";
          url = "https://codeberg.org/";
          icon = "si:codeberg";
        }
      ];
    }
    {
      title = "Social";
      links = [
        {
          title = "Reddit";
          url = "https://www.reddit.com/";
          icon = "si:reddit";
        }
        {
          title = "YouTube";
          url = "https://www.youtube.com/";
          icon = "si:youtube";
        }
        {
          title = "X";
          url = "https://x.com/home";
          icon = "si:x";
        }
      ];
    }
    {
      title = "Accounts";
      links = [
        {
          title = "Proton Mail";
          url = "https://mail.proton.me/u/1/inbox";
          icon = "si:protonmail";
        }
        {
          title = "SimpleLogin";
          url = "https://app.simplelogin.io/dashboard/";
          icon = "mdi:shield-lock-outline";
        }
      ];
    }
  ];

  marketSymbols = [
    {
      symbol = "BTC-USD";
      name = "Bitcoin";
    }
    {
      symbol = "LTC-USD";
      name = "Litecoin";
    }
    {
      symbol = "XMR-USD";
      name = "Monero";
    }
    {
      symbol = "GC=F";
      name = "Gold";
    }
    {
      symbol = "SI=F";
      name = "Silver";
    }
  ];

  serverStats = [
    {
      type = "local";
      name = "PC";
      mountpoints = {
        "/" = {
          name = "Root";
        };
        "/home" = {
          name = "Home";
        };
      };
    }
  ];

  githubRepos = [
    "rust-lang/rust"
    "YaLTeR/niri"
    "neovim/neovim"
    "glanceapp/glance"
  ];

  redditFeeds = [
    {
      subreddit = "unixporn";
      style = "vertical-list";
      limit = 10;
      collapse-after = 5;
    }
    {
      subreddit = "nixos";
      style = "vertical-list";
      limit = 10;
      collapse-after = 5;
    }
    {
      subreddit = "linux";
      style = "vertical-list";
      limit = 10;
      collapse-after = 5;
    }
  ];

  youtubeChannels = [
    "UCsBjURrPoezykLs9EqgamOA" # Fireship
    "UCUyeluBRhGPCW4rPe_UvBZQ" # ThePrimeagen
    "UCc0YbtMkRdhcqwhu3Oad-lw" # No Boilerplate
    "UC2Xd-TjJByJyK2w1zNwY0zQ" # Beyond Fireship
    "UCkVfrGwV-iG9bSsgCbrNPxQ" # Better Stack
    "UCFPTbsXLqWLHcXosYYw3D6Q" # codingjerk
    "UCW6MNdOsqv2E9AjQkv9we7A" # PwnFunction
    "UCZgt6AzoyjslHTC9dz0UoTw" # ByteByteGo
    "UCWQaM7SpSECp9FELz-cHzuQ" # Dreams of Code
    "UCW6xlqxSY3gGur4PkGPEUeA" # Seytonic
    "UCvF3C7NCZBHuE9iJvmsxO3w" # Bubble Brian
    "UC5--wS0Ljbin1TjWQX6eafA" # bigboxSWE
    "UCjREVt2ZJU8ql-NC9Gu-TJw" # Code to the Moon
    "UC7YOGHUfC1Tb6E4pudI9STA" # Mental Outlaw
    "UC_zBdZ0_H_jn41FDRG7q4Tw" # Vimjoyer
    "UCTMiGZ6t4wry5sk7Cso2plQ" # dacctal
    "UCbRP3c757lWg9M-U7TyEkXA" # Theo - t3.gg
    "UCzPpbeK8ANcNKg5aoMB0miw" # Dylan Page
    "UCXzw-OdotBUcNA9yhuYQBwA" # Awesome
  ];

  githubTrending = {
    type = "custom-api";
    title = "Trending Repos";
    cache = "24h";
    url = "https://api.ossinsight.io/v1/trends/repos/?period=past_24_hours&language=All";
    template = ''
      <ul class="list list-gap-10 collapsible-container" data-collapse-after="3">
        {{ range .JSON.Array "data.rows" }}
          <li>
            <a class="color-primary-if-not-visited" href="https://github.com/{{ .String "repo_name" }}">{{ .String "repo_name" }}</a>
            <ul class="list-horizontal-text">
              <li class="color-highlight">{{ .String "primary_language" }}</li>
              <li>{{ .String "stars" }} stars</li>
              <li>{{ .String "forks" }} forks</li>
            </ul>
            <ul class="list collapsible-container">
              <li class="color-subdue">{{ .String "description" }}</li>
            </ul>
          </li>
        {{ end }}
      </ul>
    '';
  };

  # Requires GITHUB_TOKEN via environmentFile (sops template).
  githubActivity = {
    notifications = {
      type = "custom-api";
      title = "Notifications";
      cache = "30m";
      url = "https://api.github.com/notifications?all=false&per_page=15";
      headers = {
        Authorization = "Bearer \${GITHUB_TOKEN}";
        Accept = "application/vnd.github+json";
      };
      template = ''
        <ul class="list list-gap-10 collapsible-container" data-collapse-after="5">
          {{ range .JSON.Array "" }}
            <li>
              <div class="flex items-center gap-5">
                {{ if eq (.String "reason") "assign" }}<span class="color-positive">A</span>
                {{ else if eq (.String "reason") "mention" }}<span class="color-highlight">@</span>
                {{ else if eq (.String "reason") "review_requested" }}<span class="color-primary">R</span>
                {{ else if eq (.String "reason") "subscribed" }}<span class="color-subdue">S</span>
                {{ else }}<span class="color-subdue">&bull;</span>
                {{ end }}
                <a class="color-primary-if-not-visited" href="{{ .String "subject.url" | replaceAll "api.github.com/repos" "github.com" | replaceAll "/pulls/" "/pull/" }}">{{ .String "subject.title" }}</a>
              </div>
              <div class="color-subdue text-small">{{ .String "repository.full_name" }}</div>
            </li>
          {{ else }}
            <li class="color-subdue">No new notifications</li>
          {{ end }}
        </ul>
      '';
    };

    personalRepos = {
      type = "custom-api";
      title = "My Repos";
      cache = "30m";
      url = "https://api.github.com/user/repos?affiliation=owner&sort=updated&per_page=10";
      headers = {
        Authorization = "Bearer \${GITHUB_TOKEN}";
        Accept = "application/vnd.github.v3+json";
      };
      template = ''
        <ul class="list list-gap-10 collapsible-container" data-collapse-after="5">
          {{ range .JSON.Array "" }}
            <li>
              <div class="flex items-center justify-between">
                <a class="color-primary-if-not-visited" href="{{ .String "html_url" }}">{{ .String "name" }}</a>
                <ul class="list-horizontal-text">
                  <li class="text-small color-subdue">{{ .String "language" }}</li>
                  <li class="text-small color-subdue">&#9733; {{ .Int "stargazers_count" }}</li>
                </ul>
              </div>
              <div class="color-subdue text-small margin-top-2">{{ .String "description" }}</div>
            </li>
          {{ end }}
        </ul>
      '';
    };
  };

  # --- Composite widgets ---

  searchWidget = {
    type = "search";
    search-engine = "duckduckgo";
    new-tab = true;
    bangs = searchBangs;
  };

  youtubeWidget = {
    type = "videos";
    title = "YouTube";
    style = "grid-cards";
    channels = youtubeChannels;
  };

  bookmarksWidget = {
    type = "bookmarks";
    groups = bookmarkGroups;
  };

  releasesWidget = {
    type = "releases";
    title = "Releases";
    show-source-icon = true;
    limit = 6;
    collapse-after = 3;
    token = "\${GITHUB_TOKEN}";
    repositories = githubRepos;
  };
in
{
  server = {
    host = constants.localhost;
    port = constants.ports.glance;
  };

  branding = {
    logo-text = "Y";
    app-name = "Dashboard";
    hide-footer = true;
    app-background-color = constants.color.bg;
  };

  # Gruvbox Dark theme -- derived from shared/constants.nix
  theme = {
    background-color = hexToGlanceHsl constants.color.bg;
    primary-color = hexToGlanceHsl constants.color.fg0;
    positive-color = hexToGlanceHsl constants.color.green;
    negative-color = hexToGlanceHsl constants.color.red;
    contrast-multiplier = 1.1;
  };

  pages = [
    {
      name = "Home";

      # Markets widget at top (crypto + metals)
      head-widgets = [
        {
          type = "markets";
          hide-header = true;
          markets = marketSymbols;
        }
      ];

      columns = [
        # LEFT SIDEBAR
        {
          size = "small";
          widgets = [
            searchWidget

            # Service health monitoring
            {
              type = "monitor";
              title = "Services";
              cache = "1m";
              sites = import ./_service-sites.nix { inherit constants; };
            }

            # NOTE: Tor exposes SOCKS/DNS ports (9050/9053), not an HTTP UI endpoint,
            # so it cannot be health-checked by Glance's HTTP monitor widget.

            # Docker containers
            {
              type = "docker-containers";
              format-container-names = true;
            }
          ];
        }

        # CENTER MAIN
        {
          size = "full";
          widgets = [
            {
              type = "hacker-news";
              limit = 10;
              collapse-after = 5;
              extra-sort-by = "engagement";
            }
            youtubeWidget
          ]
          ++ (map (sub: {
            type = "reddit";
            inherit (sub)
              subreddit
              style
              limit
              collapse-after
              ;
          }) redditFeeds);
        }

        # RIGHT SIDEBAR
        {
          size = "small";
          widgets = [
            {
              type = "server-stats";
              servers = serverStats;
            }
            bookmarksWidget
            releasesWidget
          ];
        }
      ];
    }
    {
      name = "Search";

      columns = [
        {
          size = "full";
          widgets = [
            searchWidget
            bookmarksWidget
          ];
        }
      ];
    }
    {
      name = "YouTube";

      columns = [
        {
          size = "full";
          widgets = [
            youtubeWidget
          ];
        }
      ];
    }
    {
      name = "GitHub";

      columns = [
        {
          size = "full";
          widgets = [
            githubTrending
            githubActivity.notifications
            githubActivity.personalRepos
            releasesWidget
          ];
        }
      ];
    }
  ];
}
