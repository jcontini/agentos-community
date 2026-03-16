#!/usr/bin/env npx tsx
/**
 * Backwards-compatible wrapper for the renamed skill scaffold generator.
 *
 * Keep this entrypoint so older docs and shell habits still work.
 */

await import('./new-skill.ts');
