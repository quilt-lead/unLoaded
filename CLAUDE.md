# Project instructions

The project mission below is the source of truth for product direction. Every design, architecture, and UI decision should be consistent with it. If a request conflicts with the mission, point out the conflict before proceeding.

@mission.md

# UI skills

UI quality is a core part of the mission, so the project vendors UI skills in [.claude/skills/](.claude/skills/) (sources and licenses: [.claude/skills/SOURCES.md](.claude/skills/SOURCES.md)). Use them for any UI work:

- **frontend-design** ([SKILL.md](.claude/skills/frontend-design/SKILL.md)): load before designing a new view or restyling an existing one. Plan the tokens (color, type, layout), check the plan against the brief, then build. This is an engineering tool for structural engineers: favor clarity, density, and legibility of calculations and element data over marketing-page treatments.
- **frontend-ui-engineering** ([SKILL.md](.claude/skills/frontend-ui-engineering/SKILL.md)): load when building or changing React components. Covers component structure, state, accessibility (WCAG 2.1 AA), and loading/empty/error states.
- **react-best-practices** ([SKILL.md](.claude/skills/react-best-practices/SKILL.md)): load when writing or reviewing React code. This app is React + TypeScript on Vite, not Next.js, so skip the `server-*` rules and Next-specific advice.
- **web-design-guidelines** ([SKILL.md](.claude/skills/web-design-guidelines/SKILL.md)): run as a review pass on finished UI code before calling UI work done.

# Agent handoff notes

Before starting work, read [docs/agents/](docs/agents/README.md): findings, decisions, gotchas and the files in flight from earlier sessions. Before handing off, add or update a note there, following its conventions.
