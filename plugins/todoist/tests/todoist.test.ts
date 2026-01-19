/**
 * Todoist Plugin Tests
 * 
 * Comprehensive tests for the Todoist plugin using API v1.
 * Requires: TODOIST_API_KEY or configured credential in AgentOS.
 * 
 * Coverage:
 * - task.list (with filters: project_id, label, parent_id)
 * - task.filter (Todoist filter queries)
 * - task CRUD (create, get, update, complete, reopen, delete)
 * - Priority mapping (AgentOS 1-4 → Todoist 4-1)
 * - Due dates (natural language)
 * - Labels on tasks
 * - Subtasks (parent_id)
 * - Moving tasks (mutation handler)
 * - project.list, label.list
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { aos, testContent, TEST_PREFIX } from '../../../tests/utils/fixtures';

const plugin = 'todoist';

// Track created items for cleanup
const createdItems: Array<{ id: string; type: 'task' | 'project' }> = [];

// Skip tests if no credentials configured
let skipTests = false;

describe('Todoist Plugin', () => {
  beforeAll(async () => {
    // Check if Todoist is configured by trying a simple list
    try {
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.list',
        params: {},
      });
    } catch (e: any) {
      if (e.message?.includes('Credential not found')) {
        console.log('  ⏭ Skipping Todoist tests: no credentials configured');
        skipTests = true;
      } else {
        throw e;
      }
    }
  });

  // Clean up after tests
  afterAll(async () => {
    // Delete tasks first (before projects)
    for (const item of createdItems.filter(i => i.type === 'task')) {
      try {
        await aos().call('UsePlugin', {
          plugin,
          tool: 'task.delete',
          params: { id: item.id },
          execute: true,
        });
      } catch (e) {
        // Task may already be deleted - ignore
      }
    }
  });

  // ===========================================================================
  // task.list
  // ===========================================================================
  describe('task.list', () => {
    it('returns an array of tasks', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.list',
        params: {},
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('tasks have all mapped fields', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.list',
        params: {},
      });

      // Check at least one task has the expected fields
      if (tasks.length > 0) {
        const task = tasks[0];
        // Required fields from adapter mapping
        expect(task.id).toBeDefined();
        expect(task.title).toBeDefined();
        expect(task.plugin).toBe(plugin);
        // Mapped fields (always present from Todoist v1 API)
        expect(typeof task.completed).toBe('boolean');
        expect(typeof task.priority).toBe('number');
        expect(task._project_id).toBeDefined();
      }
    });

    it('can filter by project_id', async () => {
      if (skipTests) return;
      
      const projects = await aos().call('UsePlugin', {
        plugin,
        tool: 'project.list',
      });
      
      if (projects.length === 0) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.list',
        params: { project_id: projects[0].id },
      });

      expect(Array.isArray(tasks)).toBe(true);
      // All returned tasks should be from this project
      for (const task of tasks) {
        expect(task._project_id).toBe(projects[0].id);
      }
    });

    it('can filter by label', async () => {
      if (skipTests) return;
      
      const labels = await aos().call('UsePlugin', {
        plugin,
        tool: 'label.list',
      });
      
      if (labels.length === 0) {
        console.log('  Skipping: no labels exist');
        return;
      }
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.list',
        params: { label: labels[0].name },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });
  });

  // ===========================================================================
  // task.filter (Todoist filter queries)
  // ===========================================================================
  describe('task.filter', () => {
    it('can query tasks due today', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.filter',
        params: { query: 'today' },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('can query overdue tasks', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.filter',
        params: { query: 'overdue' },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('can query tasks due in next 7 days', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.filter',
        params: { query: '7 days' },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('can query tasks with no due date', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.filter',
        params: { query: 'no date' },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });

    it('can query high priority tasks', async () => {
      if (skipTests) return;
      
      const tasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.filter',
        params: { query: 'p1' },
      });

      expect(Array.isArray(tasks)).toBe(true);
    });
  });

  // ===========================================================================
  // task CRUD - Basic lifecycle
  // ===========================================================================
  describe('task CRUD', () => {
    let createdTask: any;

    it('task.create - creates task with title and description', async () => {
      if (skipTests) return;

      const title = testContent('task');
      
      createdTask = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title,
          description: 'Created by AgentOS integration test',
        },
        execute: true,
      });

      expect(createdTask).toBeDefined();
      expect(createdTask.id).toBeDefined();
      expect(createdTask.title).toContain(TEST_PREFIX);
      expect(createdTask.description).toBe('Created by AgentOS integration test');
      
      createdItems.push({ id: createdTask.id, type: 'task' });
    });

    it('task.get - retrieves task with all fields', async () => {
      if (skipTests || !createdTask?.id) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: createdTask.id },
      });

      expect(task).toBeDefined();
      expect(task.id).toBe(createdTask.id);
      expect(task.title).toContain(TEST_PREFIX);
      expect(task.completed).toBe(false);
      expect(task.plugin).toBe(plugin);
    });

    it('task.update - updates title and description', async () => {
      if (skipTests || !createdTask?.id) return;

      const newTitle = testContent('updated task');
      const newDesc = 'Updated description';
      
      const updated = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: createdTask.id,
          title: newTitle,
          description: newDesc,
        },
        execute: true,
      });

      expect(updated).toBeDefined();
      
      // Verify the update
      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: createdTask.id },
      });
      
      expect(task.title).toBe(newTitle);
      expect(task.description).toBe(newDesc);
    });

    it('task.complete - marks task as completed', async () => {
      if (skipTests || !createdTask?.id) return;

      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.complete',
        params: { id: createdTask.id },
        execute: true,
      });

      // Verify task is now completed
      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: createdTask.id },
      });
      
      expect(task.completed).toBe(true);
    });

    it('task.reopen - reopens completed task', async () => {
      if (skipTests || !createdTask?.id) return;

      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.reopen',
        params: { id: createdTask.id },
        execute: true,
      });

      // Verify task is now not completed
      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: createdTask.id },
      });
      
      expect(task.completed).toBe(false);
    });

    it('task.delete - removes the task', async () => {
      if (skipTests || !createdTask?.id) return;

      const result = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: createdTask.id },
        execute: true,
      });
      
      // Delete returns empty success
      expect(result).toBeDefined();
      
      // Remove from cleanup list
      const idx = createdItems.findIndex(i => i.id === createdTask.id);
      if (idx >= 0) createdItems.splice(idx, 1);
    });
  });

  // ===========================================================================
  // Priority (Todoist scale: 1=normal, 4=urgent)
  // ===========================================================================
  describe('priority', () => {
    it('can create task with priority 4 (urgent)', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('urgent priority'),
          priority: 4,
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      expect(task.priority).toBe(4);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can create task with priority 1 (normal)', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('normal priority'),
          priority: 1,
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      expect(task.priority).toBe(1);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('default priority is 1 (normal)', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('default priority'),
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      // Default priority in Todoist is 1
      expect(task.priority).toBe(1);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can update priority from normal to urgent', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('priority update'),
          priority: 1,
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      // Update to urgent priority (need to include title to satisfy API)
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: task.id,
          title: testContent('priority updated'),
          priority: 4,
        },
        execute: true,
      });

      const updated = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });
      
      expect(updated.priority).toBe(4);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });
  });

  // ===========================================================================
  // Due dates - natural language parsing
  // ===========================================================================
  describe('due dates', () => {
    it('can create task with natural language due date', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('due tomorrow'),
          due: 'tomorrow',
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      // Should have a due_date set
      expect(task.due_date).toBeDefined();
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can create task with specific date', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('specific date'),
          due: 'Jan 31',
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      expect(task.due_date).toBeDefined();
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can update due date', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('update due'),
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      // Initially no due date
      expect(task.due_date).toBeUndefined();
      
      // Add due date
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: task.id,
          due: 'next friday',
        },
        execute: true,
      });

      const updated = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });
      
      expect(updated.due_date).toBeDefined();
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });
  });

  // ===========================================================================
  // Labels on tasks
  // ===========================================================================
  describe('labels', () => {
    it('can create task with labels', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('with labels'),
          labels: ['test-label'],
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      // Should have labels
      expect(task._labels).toBeDefined();
      expect(Array.isArray(task._labels)).toBe(true);
      expect(task._labels).toContain('test-label');
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can update task labels', async () => {
      if (skipTests) return;

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('update labels'),
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      
      // Add labels
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: task.id,
          labels: ['new-label', 'another-label'],
        },
        execute: true,
      });

      const updated = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });
      
      expect(updated._labels).toContain('new-label');
      expect(updated._labels).toContain('another-label');
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });
  });

  // ===========================================================================
  // Subtasks (parent_id)
  // ===========================================================================
  describe('subtasks', () => {
    it('can create subtask with parent_id', async () => {
      if (skipTests) return;

      // Create parent task
      const parent = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('parent task'),
        },
        execute: true,
      });

      createdItems.push({ id: parent.id, type: 'task' });

      // Create subtask
      const subtask = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('subtask'),
          parent_id: parent.id,
        },
        execute: true,
      });

      createdItems.push({ id: subtask.id, type: 'task' });
      
      expect(subtask._parent_id).toBe(parent.id);
      
      // Clean up (subtask first, then parent)
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: subtask.id },
        execute: true,
      });
      createdItems.pop();
      
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: parent.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can filter tasks by parent_id', async () => {
      if (skipTests) return;

      // Create parent task
      const parent = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('filter parent'),
        },
        execute: true,
      });

      createdItems.push({ id: parent.id, type: 'task' });

      // Create two subtasks
      const sub1 = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('subtask 1'),
          parent_id: parent.id,
        },
        execute: true,
      });
      createdItems.push({ id: sub1.id, type: 'task' });

      const sub2 = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('subtask 2'),
          parent_id: parent.id,
        },
        execute: true,
      });
      createdItems.push({ id: sub2.id, type: 'task' });

      // Filter by parent_id
      const subtasks = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.list',
        params: { parent_id: parent.id },
      });

      expect(subtasks.length).toBe(2);
      expect(subtasks.every((t: any) => t._parent_id === parent.id)).toBe(true);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: sub2.id },
        execute: true,
      });
      createdItems.pop();
      
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: sub1.id },
        execute: true,
      });
      createdItems.pop();
      
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: parent.id },
        execute: true,
      });
      createdItems.pop();
    });
  });

  // ===========================================================================
  // Moving tasks (mutation handler)
  // ===========================================================================
  describe('move task via task.update', () => {
    it('can move task to different project via task.update', async () => {
      if (skipTests) return;

      // Get projects to find a target
      const projects = await aos().call('UsePlugin', {
        plugin,
        tool: 'project.list',
      });

      if (projects.length < 2) {
        console.log('  Skipping: need at least 2 projects to test move');
        return;
      }

      // Create task in first project
      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('task to move'),
          project_id: projects[0].id,
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });
      expect(task._project_id).toBe(projects[0].id);

      // Move task by calling task.update with project_id
      // This routes through the move_task mutation handler
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: task.id,
          project_id: projects[1].id,
        },
        execute: true,
      });

      // Verify the task moved
      const movedTask = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });

      expect(movedTask._project_id).toBe(projects[1].id);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });

    it('can move task and update other fields simultaneously', async () => {
      if (skipTests) return;

      const projects = await aos().call('UsePlugin', {
        plugin,
        tool: 'project.list',
      });

      if (projects.length < 2) {
        console.log('  Skipping: need at least 2 projects');
        return;
      }

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('move and update'),
          project_id: projects[0].id,
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });

      // Move AND update title in one call
      const newTitle = testContent('moved and updated');
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: task.id,
          project_id: projects[1].id,
          title: newTitle,
        },
        execute: true,
      });

      const updated = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });

      expect(updated._project_id).toBe(projects[1].id);
      expect(updated.title).toBe(newTitle);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });
  });

  // ===========================================================================
  // move_task utility (direct call)
  // ===========================================================================
  describe('move_task utility', () => {
    it('can move task directly via move_task utility', async () => {
      if (skipTests) return;

      const projects = await aos().call('UsePlugin', {
        plugin,
        tool: 'project.list',
      });

      if (projects.length < 2) {
        console.log('  Skipping: need at least 2 projects');
        return;
      }

      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('direct move'),
          project_id: projects[0].id,
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });

      // Call move_task utility directly
      await aos().call('UsePlugin', {
        plugin,
        tool: 'move_task',
        params: {
          id: task.id,
          project_id: projects[1].id,
        },
        execute: true,
      });

      const moved = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });

      expect(moved._project_id).toBe(projects[1].id);
      
      // Clean up
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });
  });

  // ===========================================================================
  // project.list
  // ===========================================================================
  describe('project.list', () => {
    it('returns an array of projects with all fields', async () => {
      if (skipTests) return;
      
      const projects = await aos().call('UsePlugin', {
        plugin,
        tool: 'project.list',
      });

      expect(Array.isArray(projects)).toBe(true);
      expect(projects.length).toBeGreaterThan(0);
      
      for (const project of projects) {
        expect(project.id).toBeDefined();
        expect(project.name).toBeDefined();
        expect(project.plugin).toBe(plugin);
        // Optional fields
        expect('color' in project).toBe(true);
      }
    });
  });

  // ===========================================================================
  // label.list
  // ===========================================================================
  describe('label.list', () => {
    it('returns an array of labels with all fields', async () => {
      if (skipTests) return;
      
      const labels = await aos().call('UsePlugin', {
        plugin,
        tool: 'label.list',
      });

      expect(Array.isArray(labels)).toBe(true);
      
      for (const label of labels) {
        expect(label.id).toBeDefined();
        expect(label.name).toBeDefined();
        expect(label.plugin).toBe(plugin);
        // Optional fields
        expect('color' in label).toBe(true);
      }
    });
  });

  // ===========================================================================
  // Complex scenarios
  // ===========================================================================
  describe('complex scenarios', () => {
    it('full task lifecycle with all fields', async () => {
      if (skipTests) return;

      const projects = await aos().call('UsePlugin', {
        plugin,
        tool: 'project.list',
      });

      // Create task with all fields (priority 3 = medium/orange)
      const task = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.create',
        params: {
          title: testContent('full lifecycle'),
          description: 'Test all features',
          due: 'tomorrow',
          priority: 3,
          project_id: projects[0]?.id,
          labels: ['test-full'],
        },
        execute: true,
      });

      createdItems.push({ id: task.id, type: 'task' });

      // Verify all fields set correctly
      expect(task.title).toContain(TEST_PREFIX);
      expect(task.description).toBe('Test all features');
      expect(task.due_date).toBeDefined();
      expect(task.priority).toBe(3);
      expect(task._labels).toContain('test-full');
      expect(task.completed).toBe(false);

      // Update multiple fields (priority 4 = urgent/red)
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.update',
        params: {
          id: task.id,
          title: testContent('updated lifecycle'),
          priority: 4,
          labels: ['updated-label'],
        },
        execute: true,
      });

      const updated = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });

      expect(updated.priority).toBe(4);
      expect(updated._labels).toContain('updated-label');

      // Complete
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.complete',
        params: { id: task.id },
        execute: true,
      });

      // Reopen
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.reopen',
        params: { id: task.id },
        execute: true,
      });

      const reopened = await aos().call('UsePlugin', {
        plugin,
        tool: 'task.get',
        params: { id: task.id },
      });

      expect(reopened.completed).toBe(false);

      // Delete
      await aos().call('UsePlugin', {
        plugin,
        tool: 'task.delete',
        params: { id: task.id },
        execute: true,
      });
      createdItems.pop();
    });
  });
});
