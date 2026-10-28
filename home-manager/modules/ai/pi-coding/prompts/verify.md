---
description: Verify acceptance criteria and report check evidence
argument-hint: "[scope or acceptance criteria]"
---

Verify ${@:-the current implementation against its acceptance criteria}. Read repository instructions and inspect the relevant diff and existing check commands. Establish the criteria if they were not stated. Run appropriate checks within the task's safety and build-approval constraints, preserving unrelated work. Keep source files untouched; report failures rather than fixing them. Use the evidence-report format from the loaded working preferences, including failed, blocked, and unrun checks. Identify whether evidence covers the current diff or predates later edits. Report limitations rather than treating a partial check as full verification.
