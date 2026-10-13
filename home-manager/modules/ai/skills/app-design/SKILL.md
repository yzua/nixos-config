---
name: app-design
description: Design or improve web apps and dashboards through product context, layout exploration, implementation, and browser critique. Use for new screens, substantial UI redesigns, or a requested design-quality pass.
---

# App design

Make the main user task clear and efficient, and verify the result in the running
app. Keep the user's chosen scope, stack, and established design system. For a
small visual fix, inspect and verify the affected component; skip new layouts and
product-wide design work.

## Establish the task and direction

Read the app's instructions, existing screens, components, and design notes.
Identify the user, the task they need to finish, the information they need, and
what successful completion looks like. Use available context; ask only for
missing information that would materially change the design.

For dashboards, identify the decision the screen supports. Make metric units,
comparison periods, data freshness, and filter scope understandable. Choose
tables for precise comparison and charts for the patterns users need to see;
connect summaries to useful details or actions.

When visual direction is open, inspect two or three relevant references supplied
by the user or found through available browsing. Explain which specific choices
help this task: hierarchy, density, typography, navigation, or interaction.
Preserve an existing direction when the request is a focused improvement.

Use the relevant installed skills as needed, reading their instructions first:

| Need | Skill |
| --- | --- |
| Product patterns, visual direction, or a focused UX question | `ui-ux-pro-max` |
| Comparing different layouts | `prototype` |
| Defining or extending shared tokens and component states | `design-system` |
| Implementation in an existing Tailwind/shadcn stack | `ui-styling` |
| Browser inspection and interaction through the installed CLI | `chrome-devtools-cli` |

Use only skills and tools available in the current agent environment. An
unavailable helper does not require changing the stack or installing a new tool;
use the project's existing capabilities and explain any verification limit.

**Done when:** the main task, constraints, and relevant design direction are
explicit. Record enduring decisions in the project's existing design notes;
keep one-off decisions in the task response.

## Compare layouts when the structure is unresolved

Use the prototype skill to explore two or three structurally different layouts
with representative data in the real app context. Vary information hierarchy or
interaction, so the alternatives reveal a meaningful tradeoff.
Preserve prototypes through the project's existing workflow; create commits or
update issues only when that is part of the authorized task.

If the user asked to choose between alternatives, present them before building
the final version. Otherwise, select the best fit for the task and explain why.
For a supplied design or a settled layout, proceed directly to implementation.

**Done when:** the chosen structure has a reason tied to the user's task.

## Implement the complete interaction

Reuse the app's components, tokens, and content conventions. Establish a small
coherent set when starting fresh. Let the amount of information and frequency of
use determine density; make primary actions and important values easy to scan.

Exercise representative content while building: long labels, many rows, missing
values, and relevant loading, empty, error, success, or permission states. Make
filtering, sorting, selection, and drilldown behave consistently where those
interactions exist. Keep prototype fixtures distinct from production data.

**Done when:** the requested flow works with realistic content and its relevant
states, using the chosen visual direction.

## Render, critique, and improve

Run the app with its documented command. Use available browser tools to exercise
the main task and capture screenshots at representative wide and narrow widths.
Inspect the images themselves as well as the DOM and console. For a redesign,
compare before and after using the same content and viewport.

Check hierarchy, spacing, typography, density, and consistency against the chosen
direction. Also exercise keyboard navigation and focus, zoom, responsive overflow,
and the relevant states implemented above. Use existing accessibility and flow
tests, or Lighthouse when available. Add focused Playwright/axe coverage when it
fits the project's test setup and the change warrants it; establish screenshot
baselines only after visually reviewing the result.

For a substantial screen or flow, use an independent reviewer agent when
delegation is available and authorized. Give it the task, design context, running
preview or screenshots, and states to inspect. Ask for concrete observations and
priorities; keep implementation with one writer. Agent critique is a hypothesis
about usability, so distinguish it from feedback observed from real users.

Fix findings that affect task completion, accessibility, or the chosen design,
then recheck the affected flow and screenshots. Finish when the requested scope
works, relevant checks pass, and the latest rendered result has been reviewed.
If browser access or another dependency blocks verification, state exactly what
was checked and what remains unverified.

**Handoff:** link the preview or screenshots when available, explain the design
choice and checks briefly, and identify remaining issues. For usability questions
that need human evidence, suggest a concrete task for a representative user to
attempt without coaching; never claim an agent walkthrough is user testing.
