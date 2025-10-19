# Development

## Dependencies

- Use Node 20.15.0 (see `.nvmrc`).
- When changing dependencies in the UI, run this in the `/ui` folder:
  - `npm install`
  - Commit the updated `ui/package-lock.json` along with your changes.

This keeps CI images in sync and avoids lockfile mismatches.

