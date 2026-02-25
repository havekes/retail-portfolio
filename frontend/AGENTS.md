Coding Agent Guide: retail-portfolio (Frontend)

## Project Overview
`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Frontend Tech Stack**:
- Svelte 5 / SvelteKit
- TypeScript
- TailwindCSS v4
- Vite
- npm package manager

**Infrastructure**:
- Docker Compose for dev environment

## Development Workflow

**ALWAYS**: Execute frontend commands in `retail-portfolio-frontend`.

**Frontend Workflow (`docker exec retail-portfolio-frontend`)**:
1. Install dependencies: `npm install`
2. Lint and format code: `npm run lint`
3. Run type checks: `npm run check`
4. Format code: `npm run format`

**MANDATORY**: When writing or editing code, **ALWAYS** run linting, type checks, and format before submitting.
