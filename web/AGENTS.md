# web navigation card

React/Vite/TypeScript analytics panel embedded by the FastAPI control plane.
Read this card before editing pages, hooks, API client types, routing, theme, Vite config, or visible UI.
Key files: `src/`, `package.json`, `vite.config.ts`, `tsconfig.json`, and `tailwind.config.js`.

## Local invariants

- The panel talks to the existing FastAPI `/api/v1/*` surface; do not add a new backend or dashboard process.
- `provider` remains the channel field in TypeScript types, filters, labels, and charts. Do not introduce a `channel` alias.
- Keep `@/` imports aligned between `tsconfig.json` and `vite.config.ts`.
- Tailwind dark theme is the established visual base; avoid broad restyles that fight the existing theme without user direction.
- Build output belongs in `web/dist/` and remains gitignored.

## Local rules

- `npm run lint` is TypeScript checking for both app and Vite config.
- `npm run build` runs both TypeScript checks and `vite build`.
- Current repo has no committed npm lockfile; use `npm install` for first install and `npm ci` only after a lockfile exists.
- Visible UI changes should be checked in a browser with a seeded temp DB when feasible.

## Do not

- Do not commit `web/dist/`, `web/node_modules/`, TypeScript build info, or Vite emitted config JS/DTS.
- Do not add frontend-only API fields without updating backend schemas/contracts.
- Do not hardcode credentials, internal URLs, account IDs, or gateway IDs in the UI.

## Validation

- `cd web && npm run lint`
- `cd web && npm run build`
