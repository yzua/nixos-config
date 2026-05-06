# Neovim editor with LSP, completion, and modern plugins.

{ pkgs, ... }:

let
  lua = path: builtins.readFile path;
  luaModules = [
    ./lua/options.lua
    ./lua/keymaps.lua
    ./lua/diagnostics.lua
    ./lua/treesitter.lua
    ./lua/lsp.lua
    ./lua/plugins/cmp.lua
    ./lua/plugins/telescope.lua
    ./lua/plugins/neo-tree.lua
    ./lua/plugins/gitsigns.lua
    ./lua/plugins/lualine.lua
    ./lua/plugins/which-key.lua
    ./lua/plugins/indent-blankline.lua
    ./lua/plugins/comment.lua
    ./lua/plugins/autopairs.lua
    ./lua/plugins/conform.lua
    ./lua/plugins/lint.lua
    ./lua/plugins/trouble.lua
    ./lua/plugins/surround.lua
    ./lua/plugins/dap.lua
  ];
  initLuaBundle = builtins.concatStringsSep "" (map lua luaModules);
  treesitterParsers = with pkgs.vimPlugins.nvim-treesitter-parsers; [
    typescript
    tsx
    javascript
    rust
    zig
    pkgs.vimPlugins.nvim-treesitter-parsers.lua
    nix
    json
    yaml
    toml
    markdown
    markdown_inline
    bash
    html
    css
    python
    go
    vim
    vimdoc
    regex
    c
    cpp
    java
    svelte
    graphql
    dockerfile
  ];
  treesitterQueries = map (parser: parser.associatedQuery) treesitterParsers;
in
{
  imports = [
    ./plugins
  ];

  programs.neovim = {
    enable = true;
    # defaultEditor removed — EDITOR is set to "code" at system level (environment.nix)
    viAlias = true;
    vimAlias = true;
    vimdiffAlias = true;

    # ripgrep and fd provided by home.packages (cli.nix) — available system-wide
    extraPackages = with pkgs; [
      zig # Zig compiler (required by zls)
      zls
      stylua
    ];

    withRuby = false;
    withPython3 = false;

    plugins =
      (with pkgs.vimPlugins; [
        plenary-nvim
        nvim-web-devicons
        nui-nvim

        nvim-lspconfig
        conform-nvim
        nvim-lint
        trouble-nvim

        nvim-dap
        nvim-dap-ui
        nvim-dap-virtual-text

        nvim-cmp
        cmp-nvim-lsp
        cmp-buffer
        cmp-path
        cmp_luasnip
        luasnip
        friendly-snippets

        telescope-nvim
        neo-tree-nvim

        gitsigns-nvim
        lualine-nvim
        which-key-nvim
        indent-blankline-nvim
        comment-nvim
        nvim-autopairs
        nvim-surround
        vim-sleuth
      ])
      ++ treesitterParsers
      ++ treesitterQueries;

    initLua = initLuaBundle;
  };
}
