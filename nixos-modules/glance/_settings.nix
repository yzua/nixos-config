# Glance dashboard settings tree.

{ constants }:

let
  searchBangs = import ./_search-bangs.nix;
  bookmarkGroups = import ./_bookmarks.nix;
  marketSymbols = import ./_markets.nix;
  serverStats = import ./_server-stats.nix;
  githubRepos = import ./_github-releases.nix;
  redditFeeds = import ./_reddit.nix;
  githubTrending = import ./_github-trending.nix;
  githubActivity = import ./_github-activity.nix;
  hexToGlanceHsl = import ./_color-helpers.nix;

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
    channels = import ./_youtube-channels.nix;
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
            # Search with bangs
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
            # Hacker News
            {
              type = "hacker-news";
              limit = 10;
              collapse-after = 5;
              extra-sort-by = "engagement";
            }

            # YouTube feeds
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
            # System stats
            {
              type = "server-stats";
              servers = serverStats;
            }

            # Bookmarks
            bookmarksWidget

            # GitHub releases
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

            # Releases (repeated here for the GitHub-focused view)
            releasesWidget
          ];
        }
      ];
    }
  ];
}
