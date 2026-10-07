# Configure tmux's palette, focus forwarding, window controls, and clipboard.

{
  config,
  lib,
  pkgs,
  ...
}:

let
  colors = config.lib.stylix.colors.withHashtag;
  ansiPalette = [
    colors.base00
    colors.base08
    colors.base0B
    colors.base0A
    colors.base0D
    colors.base0E
    colors.base0C
    colors.base05
    colors.base03
    colors.base08
    colors.base0B
    colors.base0A
    colors.base0D
    colors.base0E
    colors.base0C
    colors.base07
  ];
  tmuxPalette = lib.concatStringsSep "\n" (
    (lib.imap0 (index: color: "set -gw 'pane-colours[${toString index}]' '${color}'") ansiPalette)
    ++ (map (index: "set -gw 'pane-colours[${toString index}]' colour${toString index}") (
      lib.range 16 255
    ))
  );
  windowBinding =
    n:
    let
      index = toString n;
    in
    ''
      bind -n M-${index} if-shell "${pkgs.tmux}/bin/tmux -S '#{socket_path}' has-session -t '#{session_id}:${index}' 2>/dev/null" "select-window -t :${index}" "new-window -t :${index} -c '#{pane_current_path}'"
    '';
in
{
  # Keep the familiar prefix and split keys; new panes inherit the current CWD.
  programs.tmux = {
    enable = true;
    baseIndex = 1;
    terminal = "tmux-256color";
    historyLimit = 10000;
    # Herdr needs FocusOut to alert when its active tab is hidden by outer tmux.
    # The palette responses below keep nested focus-triggered queries safe.
    focusEvents = true;
    # Use Shift-drag for Ghostty text selection while tmux handles the mouse.
    mouse = true;
    extraConfig = ''
      # Preserve OSC 8 web/file links and advertise them to apps such as Pi.
      set -as terminal-features ',xterm-ghostty:hyperlinks'
      # Answer palette queries inside tmux, so nested TUIs cannot receive
      # fragmented OSC 4 replies from the outer terminal as typed text.
      ${tmuxPalette}
      # Preserve modified Enter keys for apps running through tmux (such as Pi).
      set -g extended-keys on
      set -g extended-keys-format csi-u
      set -g renumber-windows on
      set -g status-interval 10
      set -g status-style 'fg=${colors.base05},bg=${colors.base01}'
      set -g status-left-length 20
      set -g status-left '#[fg=${colors.base0C},bold] ● #S #[fg=${colors.base03},nobold]│ '
      set -g status-right-length 28
      set -g status-right '#[fg=${colors.base0A},bold]#{?pane_in_mode,COPY ,}#[fg=${colors.base0C}]#{b:pane_current_path} #[fg=${colors.base03}]│ #[fg=${colors.base05}]%H:%M '
      set -g window-status-style 'fg=${colors.base04},bg=${colors.base01}'
      set -g window-status-current-style 'fg=${colors.base0A},bg=${colors.base01},bold'
      set -g window-status-separator '#[fg=${colors.base03}] │ #[default]'
      set -g window-status-format ' #I:#W#{window_flags} '
      set -g window-status-current-format ' #I:#W#{window_flags} '
      set -g pane-border-style 'fg=${colors.base02}'
      set -g pane-active-border-style 'fg=${colors.base0D}'
      set -g message-style 'fg=${colors.base00},bg=${colors.base0A}'
      set -g mode-style 'fg=${colors.base00},bg=${colors.base0D}'
      bind c new-window -c "#{pane_current_path}"
      bind '"' split-window -v -c "#{pane_current_path}"
      bind % split-window -h -c "#{pane_current_path}"
      bind -r h select-pane -L
      bind -r j select-pane -D
      bind -r k select-pane -U
      bind -r l select-pane -R
      bind -r H resize-pane -L 5
      bind -r J resize-pane -D 5
      bind -r K resize-pane -U 5
      bind -r L resize-pane -R 5
      # Alt+digits switch to a window or create it in the current directory.
      ${lib.concatMapStringsSep "\n" windowBinding (lib.range 1 9)}
      bind -n M-t new-window -c "#{pane_current_path}"
      bind -n M-n next-window
      bind -n M-p previous-window
      bind -n M-q confirm-before -p 'Close window #I:#W? (y/n)' kill-window
      bind -n M-h select-pane -L
      bind -n M-j select-pane -D
      bind -n M-k select-pane -U
      bind -n M-l select-pane -R
      # Keep tmux mouse selection and keyboard copy mode in the Wayland clipboard.
      bind -T copy-mode MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel '${pkgs.wl-clipboard}/bin/wl-copy'
      bind -T copy-mode M-w send-keys -X copy-pipe-and-cancel '${pkgs.wl-clipboard}/bin/wl-copy'
      bind -T copy-mode C-w send-keys -X copy-pipe-and-cancel '${pkgs.wl-clipboard}/bin/wl-copy'
      bind -T copy-mode WheelUpPane select-pane \; send-keys -X -N 3 scroll-up
      bind -T copy-mode WheelDownPane select-pane \; send-keys -X -N 3 scroll-down
      bind r source-file ${lib.escapeShellArg "${config.xdg.configHome}/tmux/tmux.conf"} \; display-message 'tmux config reloaded'
    '';
  };
}
