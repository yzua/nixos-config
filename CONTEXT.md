# Workstation concepts

This repository manages independent NixOS and standalone Home Manager generations through a preview-before-switch workflow, voice actions with resettable conversation context, and persistent subagent sessions.

## Language

### Configuration generations

**Saved preview build**:
The store path retained by the latest preview for a selected output. Each output retains its own preview, even if another output is previewed later or describes the same store path. It is eligible for activation only while it matches that output's current desired store path; saving it does not imply that a person has reviewed it.
_Avoid_: Reviewed build

**Desired generation**:
The generation currently described by the selected flake output, whether or not it has been built or activated.

**Active generation**:
The generation currently selected for the running system or the caller's Home Manager profile; it may differ from both the desired generation and the saved preview build.

**Home output owner**:
The user and home directory declared by a selected Home Manager output. Only that matching caller can meaningfully compare the output with their active Home Manager generation, files, and session settings, or activate it. Building the output alone does not require this match.

### Voice actions

**Voice action**:
A spoken request for execution, rather than text insertion through ordinary dictation.

**Voice action context**:
The conversation history shared by successive voice actions until a reset starts a fresh history.
_Avoid_: Recording session

### Subagents

**Subagent session**:
The persistent conversation associated with a subagent's identity and allowed tools, continued by later follow-up requests.

**Subagent run**:
One execution of a subagent, started by an initial task or by resuming a completed session. Steering an active subagent stays within its current run.

**Subagent loadout**:
The resolved identity, model, permitted tools, and working context retained for a subagent session. Later runs preserve that loadout rather than adopting edits to the original agent definition.

### Shared skills

**Pinned skill source**:
The exact upstream revision selected as the baseline for a group of skills.

**Installed skill**:
A writable, caller-owned copy of a skill used by the configured agents. It is distinct from the pinned skill source and may contain personal edits.
