/**
 * PostHog Adapter Tests
 *
 * Tests for product analytics — events, persons, and session recordings.
 * Requires: PostHog Personal API Key configured in AgentOS.
 *
 * Coverage:
 * - get_projects (utility)
 * - person.list
 * - person.get
 * - person.search
 * - event.list
 * - get_event_definitions (utility)
 * - query (utility — HogQL)
 * - list_recordings (utility)
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';

const adapter = 'posthog';

let skipTests = false;
let projectId: string;
let personUuid: string;

describe('PostHog Adapter', () => {
  beforeAll(async () => {
    // Check if PostHog is configured by trying to list projects
    try {
      const projects = await aos().call('UseAdapter', {
        adapter,
        tool: 'get_projects',
        params: {},
      }) as Array<{ id: number; name: string }>;

      expect(projects.length).toBeGreaterThan(0);
      projectId = String(projects[0].id);
    } catch (e: unknown) {
      const error = e as Error;
      if (error.message?.includes('Credential not found') || error.message?.includes('No credentials')) {
        console.log('  ⏭ Skipping PostHog tests: no credentials configured');
        skipTests = true;
      } else {
        throw e;
      }
    }
  }, 30000);

  // ===========================================================================
  // get_projects
  // ===========================================================================
  describe('get_projects', () => {
    it('returns an array of projects with id and name', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'get_projects',
        params: {},
      }) as Array<{ id: number; name: string; uuid: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);

      for (const project of results) {
        expect(project.id).toBeDefined();
        expect(typeof project.id).toBe('number');
        expect(project.name).toBeDefined();
        expect(typeof project.name).toBe('string');
      }
    });
  });

  // ===========================================================================
  // person.list
  // ===========================================================================
  describe('person.list', () => {
    it('returns an array of persons', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.list',
        params: { project_id: projectId, limit: 3, offset: 0 },
      }) as Array<{ id: string; name: string; type: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results.length).toBeLessThanOrEqual(3);

      // Save a person UUID for person.get test
      personUuid = results[0].id;

      for (const person of results) {
        expect(person.id).toBeDefined();
        expect(person.type).toBe('person');
      }
    });

    it('works without optional limit/offset params', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.list',
        params: { project_id: projectId },
      }) as unknown[];

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // person.get
  // ===========================================================================
  describe('person.get', () => {
    it('returns a single person by UUID', async () => {
      if (skipTests) return;
      if (!personUuid) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.get',
        params: { project_id: projectId, id: personUuid },
      }) as { id: string; name: string; type: string; data: Record<string, unknown> };

      expect(result).toBeDefined();
      expect(result.id).toBe(personUuid);
      expect(result.type).toBe('person');
    });
  });

  // ===========================================================================
  // person.search
  // ===========================================================================
  describe('person.search', () => {
    it('searches persons by query', async () => {
      if (skipTests) return;

      // Search for a term that should match at least something
      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'person.search',
        params: { project_id: projectId, query: '@', limit: 3 },
      }) as Array<{ id: string; name: string }>;

      expect(Array.isArray(results)).toBe(true);
      // '@' should match email addresses
      expect(results.length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // event.list
  // ===========================================================================
  describe('event.list', () => {
    it('returns recent events', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.list',
        params: { project_id: projectId, limit: 3 },
      }) as Array<{ id: string; title: string; type: string; start: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);
      expect(results.length).toBeLessThanOrEqual(3);

      for (const event of results) {
        expect(event.id).toBeDefined();
        expect(event.title).toBeDefined();
        expect(event.type).toBe('event');
        expect(event.start).toBeDefined();
      }
    });

    it('filters events by name', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.list',
        params: { project_id: projectId, event: '$pageview', limit: 2 },
      }) as Array<{ title: string }>;

      expect(Array.isArray(results)).toBe(true);
      for (const event of results) {
        expect(event.title).toBe('$pageview');
      }
    });
  });

  // ===========================================================================
  // event.get
  // ===========================================================================
  describe('event.get', () => {
    it('returns a single event by ID', async () => {
      if (skipTests) return;

      // First get an event ID from event.list
      const events = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.list',
        params: { project_id: projectId, limit: 1 },
      }) as Array<{ id: string; title: string; type: string }>;

      expect(events.length).toBeGreaterThan(0);

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.get',
        params: { project_id: projectId, id: events[0].id },
      }) as { id: string; title: string; type: string };

      expect(result).toBeDefined();
      expect(result.id).toBe(events[0].id);
      expect(result.type).toBe('event');
    });
  });

  // ===========================================================================
  // get_event_definitions
  // ===========================================================================
  describe('get_event_definitions', () => {
    it('returns event definitions with names', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'get_event_definitions',
        params: { project_id: projectId, limit: 10 },
      }) as Array<{ id: string; name: string }>;

      expect(Array.isArray(results)).toBe(true);
      expect(results.length).toBeGreaterThan(0);

      for (const def of results) {
        expect(def.name).toBeDefined();
        expect(typeof def.name).toBe('string');
      }
    });
  });

  // ===========================================================================
  // query (HogQL)
  // ===========================================================================
  describe('query', () => {
    it('runs a HogQL query and returns results', async () => {
      if (skipTests) return;

      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'query',
        params: {
          project_id: projectId,
          hogql: 'SELECT event, count() as cnt FROM events WHERE timestamp > now() - interval 7 day GROUP BY event ORDER BY cnt DESC LIMIT 5',
        },
      }) as { columns: string[]; results: unknown[][] };

      expect(result).toBeDefined();
      expect(result.columns).toBeDefined();
      expect(Array.isArray(result.columns)).toBe(true);
      expect(result.columns).toContain('event');
      expect(result.columns).toContain('cnt');
      expect(result.results).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
    });
  });

  // ===========================================================================
  // list_recordings
  // ===========================================================================
  describe('list_recordings', () => {
    it('returns session recordings metadata', async () => {
      if (skipTests) return;

      const results = await aos().call('UseAdapter', {
        adapter,
        tool: 'list_recordings',
        params: { project_id: projectId, limit: 3 },
      }) as Array<{ id: string; distinct_id: string; start_time: string }>;

      expect(Array.isArray(results)).toBe(true);
      // May be empty if no recordings — just check it doesn't error
      if (results.length > 0) {
        expect(results[0].id).toBeDefined();
      }
    });
  });
});
