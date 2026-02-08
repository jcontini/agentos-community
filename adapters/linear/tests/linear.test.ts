/**
 * Linear Adapter Tests
 * 
 * Tests CRUD operations for the Linear adapter.
 * Requires: LINEAR_API_KEY or configured credential in AgentOS.
 * 
 * Note: Linear requires a team_id for creating issues.
 * The test will auto-discover the first available team.
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { aos, testContent, TEST_PREFIX } from '@test/fixtures';

const adapter = 'linear';
const account = 'AgentOS';
const baseParams = { adapter, account };

// Track created items for cleanup
const createdItems: Array<{ id: string }> = [];

// Team ID discovered at runtime
let teamId: string | undefined;

// Skip tests if no credentials configured
let skipTests = false;

describe('Linear Adapter', () => {
  beforeAll(async () => {
    try {
      // Get the first available team for creating issues
      const teams = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'get_teams',
        params: {},
      });
      
      if (teams.length > 0) {
        teamId = teams[0].id;
        console.log(`  Using team: ${teams[0].name || teamId}`);
      }
    } catch (e: any) {
      if (e.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping Linear tests: no credentials configured');
        skipTests = true;
      } else {
        throw e;
      }
    }
  });

  // Clean up after tests
  afterAll(async () => {
    for (const item of createdItems) {
      try {
        await aos().call('UseAdapter', {
          ...baseParams,
          tool: 'task.delete',
          params: { id: item.id },
          execute: true,
        });
      } catch (e) {
        console.warn(`  Failed to cleanup task ${item.id}:`, e);
      }
    }
  });

  describe('task.list', () => {
    it('returns an array of tasks', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.list',
        params: { limit: 5 },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('tasks have required schema fields', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.list',
        params: { limit: 5 },
      });

      for (const task of tasks) {
        expect(task.id).toBeDefined();
        expect(task.name).toBeDefined();
        expect(task.adapter).toBe(adapter);
        
        // Linear-specific: should have source_id (e.g., "AGE-123")
        expect(task.source_id).toBeDefined();
      }
    });

    it('tasks have data.completed boolean field', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.list',
        params: { limit: 5 },
      });

      // The adapter mapping has: data.completed: '.state.type == "completed"'
      for (const task of tasks) {
        expect(typeof task['data.completed']).toBe('boolean');
      }
    });

    it('respects limit parameter', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.list',
        params: { limit: 3 },
      });

      expect(tasks.length).toBeLessThanOrEqual(3);
    });
  });

  describe('task CRUD: create → get → update → delete', () => {
    let createdTask: any;

    it('can create a task', async () => {
      if (skipTests) return;
      if (!teamId) {
        console.log('  Skipping: no team_id discovered');
        return;
      }

      const title = testContent('task');
      
      createdTask = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.create',
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
      if (skipTests) return;
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const task = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.get',
        params: { id: createdTask.id },
      });

      expect(task).toBeDefined();
      expect(task.id).toBe(createdTask.id);
      expect(task.name).toContain(TEST_PREFIX);
    });

    it('can update the task', async () => {
      if (skipTests) return;
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const newTitle = testContent('updated task');
      
      const updated = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.update',
        params: {
          id: createdTask.id,
          name: newTitle,
        },
        execute: true,
      });

      expect(updated).toBeDefined();
    });

    it('can delete the task', async () => {
      if (skipTests) return;
      if (!createdTask?.id) {
        console.log('  Skipping: no task was created');
        return;
      }

      const result = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.delete',
        params: { id: createdTask.id },
        execute: true,
      });

      expect(result).toBeDefined();
      
      // Remove from cleanup list
      const idx = createdItems.findIndex(i => i.id === createdTask.id);
      if (idx >= 0) createdItems.splice(idx, 1);
    });
  });

  describe('project.list', () => {
    it('can list projects', async () => {
      if (skipTests) return;
      
      const projects = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'project.list',
        params: {},
      });

      expect(Array.isArray(projects)).toBe(true);
      
      for (const project of projects) {
        expect(project.id).toBeDefined();
        expect(project.name).toBeDefined();
      }
    });
  });

  describe('utilities', () => {
    it('setup returns organization, teams, and viewer info', async () => {
      if (skipTests) return;
      
      const result = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'setup',
        params: {},
      });

      expect(result).toBeDefined();
      expect(result.organization).toBeDefined();
      expect(result.organization.urlKey).toBeDefined();
      expect(result.teams).toBeDefined();
      expect(Array.isArray(result.teams)).toBe(true);
      expect(result.viewer).toBeDefined();
    });

    it('get_organization returns org info', async () => {
      if (skipTests) return;
      
      const org = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'get_organization',
        params: {},
      });

      expect(org).toBeDefined();
      expect(org.id).toBeDefined();
      expect(org.urlKey).toBeDefined();
    });

    it('whoami returns current user', async () => {
      if (skipTests) return;
      
      const user = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'whoami',
        params: {},
      });

      expect(user).toBeDefined();
      expect(user.id).toBeDefined();
      expect(user.email).toBeDefined();
    });

    it('get_teams returns teams', async () => {
      if (skipTests) return;
      
      const teams = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'get_teams',
        params: {},
      });

      expect(Array.isArray(teams)).toBe(true);
      if (teams.length > 0) {
        expect(teams[0].id).toBeDefined();
        expect(teams[0].name).toBeDefined();
      }
    });

    it('get_workflow_states returns states for a team', async () => {
      if (skipTests) return;
      if (!teamId) {
        console.log('  Skipping: no team_id discovered');
        return;
      }
      
      const states = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'get_workflow_states',
        params: { team_id: teamId },
      });

      expect(Array.isArray(states)).toBe(true);
      if (states.length > 0) {
        expect(states[0].id).toBeDefined();
        expect(states[0].name).toBeDefined();
        expect(states[0].type).toBeDefined();
      }
    });

    it('get_cycles returns cycles for a team', async () => {
      if (skipTests) return;
      if (!teamId) {
        console.log('  Skipping: no team_id discovered');
        return;
      }
      
      const cycles = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'get_cycles',
        params: { team_id: teamId },
      });

      expect(Array.isArray(cycles)).toBe(true);
      // Cycles may be empty if team doesn't use them
    });
  });

  describe('relationship utilities', () => {
    let task1: any;
    let task2: any;
    let blockerRelationId: string | undefined;
    let relatedRelationId: string | undefined;

    it('get_relations returns relationship data', async () => {
      if (skipTests) return;
      
      // Get relations for any existing task
      const tasks = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.list',
        params: { limit: 1 },
      });

      if (tasks.length === 0) {
        console.log('  Skipping: no tasks available');
        return;
      }

      const relations = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'get_relations',
        params: { id: tasks[0].id },
      });

      expect(relations).toBeDefined();
      // Relations may be empty arrays, but should be defined
      expect(Array.isArray(relations.blocks) || relations.blocks === undefined).toBe(true);
    });

    it('can create two tasks for relationship testing', async () => {
      if (skipTests) return;
      if (!teamId) {
        console.log('  Skipping: no team_id discovered');
        return;
      }

      task1 = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.create',
        params: {
          name: testContent('task1 for relations'),
          team_id: teamId,
        },
        execute: true,
      });
      createdItems.push({ id: task1.id });

      task2 = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'task.create',
        params: {
          name: testContent('task2 for relations'),
          team_id: teamId,
        },
        execute: true,
      });
      createdItems.push({ id: task2.id });

      expect(task1.id).toBeDefined();
      expect(task2.id).toBeDefined();
    });

    it('add_blocker creates blocking relationship and returns operation_result', async () => {
      if (skipTests) return;
      if (!task1?.id || !task2?.id) {
        console.log('  Skipping: tasks not created');
        return;
      }

      const result = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'add_blocker',
        params: { id: task1.id, blocker_id: task2.id },
        execute: true,
      });

      expect(result.success).toBe(true);
      expect(result.id).toBeDefined(); // relation ID in standard `id` field
      blockerRelationId = result.id;
    });

    it('remove_relation removes blocking relationship', async () => {
      if (skipTests) return;
      if (!blockerRelationId) {
        console.log('  Skipping: no blocker relation created');
        return;
      }

      const result = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'remove_relation',
        params: { relation_id: blockerRelationId },
        execute: true,
      });

      expect(result.success).toBe(true);
    });

    it('add_related links two issues and returns operation_result', async () => {
      if (skipTests) return;
      if (!task1?.id || !task2?.id) {
        console.log('  Skipping: tasks not created');
        return;
      }

      const result = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'add_related',
        params: { id: task1.id, related_id: task2.id },
        execute: true,
      });

      expect(result.success).toBe(true);
      expect(result.id).toBeDefined(); // relation ID in standard `id` field
      relatedRelationId = result.id;
    });

    it('remove_relation removes related relationship', async () => {
      if (skipTests) return;
      if (!relatedRelationId) {
        console.log('  Skipping: no related relation created');
        return;
      }

      const result = await aos().call('UseAdapter', {
        ...baseParams,
        tool: 'remove_relation',
        params: { relation_id: relatedRelationId },
        execute: true,
      });

      expect(result.success).toBe(true);
    });

    it('cleanup: delete relationship test tasks', async () => {
      if (skipTests) return;
      
      for (const task of [task1, task2]) {
        if (task?.id) {
          try {
            await aos().call('UseAdapter', {
              ...baseParams,
              tool: 'task.delete',
              params: { id: task.id },
              execute: true,
            });
            const idx = createdItems.findIndex(i => i.id === task.id);
            if (idx >= 0) createdItems.splice(idx, 1);
          } catch (e) {
            // Ignore cleanup errors
          }
        }
      }
    });
  });

});
