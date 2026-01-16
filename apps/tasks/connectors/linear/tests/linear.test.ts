/**
 * Linear Connector Tests
 * 
 * Tests CRUD operations for the Linear connector.
 * Requires: LINEAR_API_KEY or configured credential in AgentOS.
 * 
 * Note: Linear requires a team_id for creating issues.
 * The test will auto-discover the first available team.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { aos, testContent, TEST_PREFIX } from '../../../../../tests/utils/fixtures';

const app = 'linear';
const account = 'AgentOS';
const baseParams = { app, account };

// Track created items for cleanup
const createdItems: Array<{ id: string }> = [];

// Team ID discovered at runtime
let teamId: string | undefined;

describe('Linear Connector', () => {
  beforeAll(async () => {
    // Get the first available team for creating issues
    const tasks = await aos().call('Apps', {
      ...baseParams,
      action: 'list',
      params: { limit: 1 },
    });
    
    if (tasks.length > 0 && tasks[0].team?.id) {
      teamId = tasks[0].team.id;
      console.log(`  Using team: ${tasks[0].team.name || teamId}`);
    }
  });

  // Clean up after tests
  afterAll(async () => {
    for (const item of createdItems) {
      try {
        await aos().call('Apps', {
          ...baseParams,
          action: 'delete',
          params: { id: item.id },
          execute: true,
        });
      } catch (e) {
        console.warn(`  Failed to cleanup task ${item.id}:`, e);
      }
    }
  });

  describe('list', () => {
    it('returns an array of tasks', async () => {
      const tasks = await aos().call('Apps', {
        ...baseParams,
        action: 'list',
        params: { limit: 5 },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('tasks have required schema fields', async () => {
      const tasks = await aos().call('Apps', {
        ...baseParams,
        action: 'list',
        params: { limit: 5 },
      });

      for (const task of tasks) {
        expect(task.id).toBeDefined();
        expect(task.title).toBeDefined();
        expect(task.connector).toBe(app);
        
        // Linear-specific: should have source_id (e.g., "AGE-123")
        expect(task.source_id).toBeDefined();
      }
    });

    it('respects limit parameter', async () => {
      const tasks = await aos().call('Apps', {
        ...baseParams,
        action: 'list',
        params: { limit: 3 },
      });

      expect(tasks.length).toBeLessThanOrEqual(3);
    });
  });

  describe('create → get → update → delete', () => {
    let createdTask: any;

    it('can create a task', async () => {
      if (!teamId) {
        console.log('  Skipping: no team_id discovered');
        return;
      }

      const title = testContent('task');
      
      createdTask = await aos().call('Apps', {
        ...baseParams,
        action: 'create',
        params: {
          title,
          description: 'Created by AgentOS integration test',
          team_id: teamId,
        },
        execute: true,
      });

      expect(createdTask).toBeDefined();
      expect(createdTask.id).toBeDefined();
      expect(createdTask.source_id).toBeDefined(); // e.g., "AGE-271"
      
      createdItems.push({ id: createdTask.id });
    });

    it('can get the created task', async () => {
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const task = await aos().call('Apps', {
        ...baseParams,
        action: 'get',
        params: { id: createdTask.id },
      });

      expect(task).toBeDefined();
      expect(task.id).toBe(createdTask.id);
      expect(task.title).toContain(TEST_PREFIX);
    });

    it('can update the task', async () => {
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const newTitle = testContent('updated task');
      
      const updated = await aos().call('Apps', {
        ...baseParams,
        action: 'update',
        params: {
          id: createdTask.id,
          title: newTitle,
        },
        execute: true,
      });

      expect(updated).toBeDefined();
    });

    it('can complete the task', async () => {
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const result = await aos().call('Apps', {
        ...baseParams,
        action: 'complete',
        params: { id: createdTask.id },
        execute: true,
      });

      expect(result).toBeDefined();
    });

    it('can delete the task', async () => {
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const result = await aos().call('Apps', {
        ...baseParams,
        action: 'delete',
        params: { id: createdTask.id },
        execute: true,
      });

      expect(result).toBeDefined();
      
      // Remove from cleanup list
      const idx = createdItems.findIndex(i => i.id === createdTask.id);
      if (idx >= 0) createdItems.splice(idx, 1);
    });
  });

  describe('projects', () => {
    it('can list projects', async () => {
      const projects = await aos().call('Apps', {
        ...baseParams,
        action: 'projects',
      });

      expect(Array.isArray(projects)).toBe(true);
      
      for (const project of projects) {
        expect(project.id).toBeDefined();
        expect(project.name).toBeDefined();
      }
    });
  });

  describe('Linear-specific: relationship actions', () => {
    // Note: add_blocker, remove_blocker, add_related, remove_related
    // These are complex to test (need 2 tasks) - skip for now
    it.todo('can add and remove blockers');
    it.todo('can add and remove related issues');
  });
});
