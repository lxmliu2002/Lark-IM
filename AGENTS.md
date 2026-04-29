# Agent Instructions

This repository is a prototype for Agent-Pilot, an IM-driven collaborative office assistant. Keep changes focused on the demo loop: IM command input, Agent planning, Doc/Canvas/Slides generation, delivery, and multi-device sync.

## Project Shape

- `index.html` is the static app entry.
- `styles.css` owns layout and UI styling.
- `src/app.js` owns local Agent planning, generated artifacts, state sync, offline queue behavior, and rendering.
- `docs/architecture.md` explains the intended production architecture.

## Working Rules

- Prefer dependency-free changes unless a user explicitly asks for a framework migration.
- Keep the app runnable by opening `index.html` directly in a browser.
- Preserve the two-device demonstration: desktop and mobile views must both remain visible and synchronized.
- When changing sync behavior, test online updates, offline queueing, and reconnect replay.
- Use concise Chinese UI copy for user-facing labels unless the surrounding UI is already English.
