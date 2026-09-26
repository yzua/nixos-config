# Enable KeePassXC and browser integration without managing password databases.

{
  # KeePassXC and its browser native-messaging host; databases stay outside Nix.
  programs.keepassxc.enable = true;
}
