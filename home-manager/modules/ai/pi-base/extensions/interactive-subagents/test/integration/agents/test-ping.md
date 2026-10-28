---
name: test-ping
description: Integration test agent — asks the parent a question
model: anthropic/claude-haiku-4-5
tools: read, bash
disable-model-invocation: true
---

Call `ask_question` once with `question` set to `"PING: "` followed by the task
text. Stop and wait for the parent's reply; after receiving it, return a short
acknowledgement.
