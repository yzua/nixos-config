# Configuration generations

This repository manages independent NixOS and standalone Home Manager generations through a preview-before-switch workflow.

## Language

**Saved preview build**:
The store path retained by the latest preview for a selected output. Each output retains its own preview, even if another output is previewed later or describes the same store path. It is eligible for activation only while it matches that output's current desired store path; saving it does not imply that a person has reviewed it.
_Avoid_: Reviewed build

**Desired generation**:
The generation currently described by the selected flake output, whether or not it has been built or activated.

**Active generation**:
The generation currently selected for the running system or the caller's Home Manager profile; it may differ from both the desired generation and the saved preview build.
