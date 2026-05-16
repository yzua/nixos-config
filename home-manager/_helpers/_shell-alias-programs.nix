# Shared helper to set shell aliases in both zsh and bash.
# Used by language modules and the global zsh aliases module.

{ shellAliases }:
{
  zsh.shellAliases = shellAliases;
  bash.shellAliases = shellAliases;
}
