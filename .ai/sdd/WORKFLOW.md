# SDD Workflow Guide

A lightweight Spec-Driven Development pipeline for MAAS.

## Pipeline

```text
IDEA -> PLAN -> REQUIREMENTS -> DESIGN -> TASKS -> IMPLEMENTATION -> REVIEW
```

- `IDEA`: divergent exploration before planning. No commitment yet.
- `PLAN`: optional for small work, recommended for medium projects.
- `REQUIREMENTS`: business/product contract (WHAT/WHY).
- `DESIGN`: technical contract (HOW/trade-offs).
- `TASKS`: implementation plan (HOW MUCH, dependencies).
- `IMPLEMENTATION`: code execution against approved specs.
- `REVIEW`: verifies implementation against requirements, design, tasks.

## Directory Structure

```text
.ai/
  steering/
    product.md
    tech-stack.md
    conventions.md
  sdd/
    INDEX.md
    WORKFLOW.md
    PLAN.md               # optional
    handoff/
      sdd-brief.md         # generated after tasks:approved or review:done
    ideas/
      001-feature-idea.md
    specs/
      001-feature-name/
        .status
        requirements.md
        design.md
        tasks.md
        review.md
        decisions.md       # optional
```

## Status Values

```text
idea:exploring
idea:captured
plan:draft
plan:approved
requirements:draft
requirements:approved
design:draft
design:approved
tasks:draft
tasks:approved
implementation:in-progress
implementation:done
review:done
```

## Gate Rules

- No binding `design.md` before `requirements:approved` (unless explicit draft spike).
- No binding `tasks.md` before `design:approved` (unless explicit draft planning).
- No code before `tasks:approved`.
- `.status` is the source of truth; file existence does not imply approval.

## Feature Numbering

Feature spec directories: `.ai/sdd/specs/NNN-feature-slug/`. Determine `NNN` from the
filesystem every time (max existing prefix + 1, zero-padded to 3 digits), never from memory
or from `INDEX.md`.

## Commands

- `/skill:sdd-idea` — explore a raw idea.
- `/skill:sdd-plan` — roadmap/feature mapping.
- `/skill:sdd-prd` — requirements for a known feature.
- `/skill:sdd-spec` — architecture/design after approved requirements.
- `/skill:sdd-tasks` — task breakdown after approved design.
- `/skill:sdd-exec` — implement an approved task.
- `/skill:sdd-review` — verify implementation against specs.
- `/skill:sdd-status` — check progress/blockers/next action.
