# Opt-in Numtide cache for prebuilt AI packages on hosts that trust its key.

{ lib, ... }:

{
  # This host opts in to Numtide's prebuilt llm-agents.nix packages. The key
  # is published by the upstream flake and must be reviewed before activation.
  nix.settings.substituters = lib.mkAfter [ "https://cache.numtide.com" ];
  nix.settings.trusted-public-keys = [
    "niks3.numtide.com-1:DTx8wZduET09hRmMtKdQDxNNthLQETkc/yaX7M4qK0g="
  ];
}
