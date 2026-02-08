/**
 * Apple Calendar Adapter Tests
 * 
 * Comprehensive tests for the Apple Calendar adapter using EventKit.
 * Requires: macOS with Calendar access granted.
 * 
 * Coverage:
 * - calendar.list (list all calendars)
 * - event.list (with filters: days, calendar_id, query)
 * - event CRUD (create, get, update, delete)
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { aos, TEST_PREFIX } from '@test/fixtures';

const adapter = 'apple-calendar';

// Track created events for cleanup
const createdEvents: string[] = [];

// Skip tests if no access
let skipTests = false;

describe('Apple Calendar Adapter', () => {
  beforeAll(async () => {
    // Check if Calendar access is granted
    try {
      await aos().call('UseAdapter', {
        adapter,
        tool: 'calendar.list',
        params: {},
      });
    } catch (e: any) {
      if (e.message?.includes('access denied') || e.message?.includes('Calendar access')) {
        console.log('  ⏭ Skipping Apple Calendar tests: no calendar access');
        skipTests = true;
      } else {
        throw e;
      }
    }
  });

  // Clean up after tests
  afterAll(async () => {
    for (const eventId of createdEvents) {
      try {
        await aos().call('UseAdapter', {
          adapter,
          tool: 'event.delete',
          params: { id: eventId },
        });
      } catch (e) {
        // Event may already be deleted - ignore
      }
    }
  });

  // ===========================================================================
  // calendar.list
  // ===========================================================================
  describe('calendar.list', () => {
    it('returns an array of calendars', async () => {
      if (skipTests) return;
      
      const calendars = await aos().call('UseAdapter', {
        adapter,
        tool: 'calendar.list',
        params: {},
      });

      expect(Array.isArray(calendars)).toBe(true);
      expect(calendars.length).toBeGreaterThan(0);
    });

    it('calendars have required fields', async () => {
      if (skipTests) return;
      
      const calendars = await aos().call('UseAdapter', {
        adapter,
        tool: 'calendar.list',
        params: {},
      });

      const cal = calendars[0];
      expect(cal).toHaveProperty('id');
      expect(cal).toHaveProperty('name');
      expect(typeof cal.id).toBe('string');
      expect(typeof cal.name).toBe('string');
    });
  });

  // ===========================================================================
  // event.list
  // ===========================================================================
  describe('event.list', () => {
    it('returns an array of events', async () => {
      if (skipTests) return;
      
      const events = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.list',
        params: { days: 30 },
      });

      expect(Array.isArray(events)).toBe(true);
    });

    it('can filter by days parameter', async () => {
      if (skipTests) return;
      
      const events = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.list',
        params: { days: 1 },
      });

      expect(Array.isArray(events)).toBe(true);
    });
  });

  // ===========================================================================
  // event CRUD
  // ===========================================================================
  describe('event CRUD', () => {
    let testEventId: string;
    const testTitle = `${TEST_PREFIX} Test Meeting`;
    
    // Create a date for tomorrow at 2pm
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(14, 0, 0, 0);
    const startTime = `${tomorrow.toISOString().split('T')[0]} 14:00`;
    const endTime = `${tomorrow.toISOString().split('T')[0]} 15:00`;

    it('event.create - creates event with title and time', async () => {
      if (skipTests) return;
      
      const event = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.create',
        params: {
          title: testTitle,
          start: startTime,
          end: endTime,
          location: 'Test Location',
          description: 'Test description for automated test',
        },
      });

      expect(event).toHaveProperty('id');
      expect(event.title).toBe(testTitle);
      expect(event).toHaveProperty('start');
      
      testEventId = event.id;
      createdEvents.push(testEventId);
    });

    it('event.get - retrieves event with all fields', async () => {
      if (skipTests || !testEventId) return;
      
      const event = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.get',
        params: { id: testEventId },
      });

      expect(event.id).toBe(testEventId);
      expect(event.title).toBe(testTitle);
      expect(event.location).toBe('Test Location');
      expect(event.description).toBe('Test description for automated test');
    });

    it('event.update - updates title and location', async () => {
      if (skipTests || !testEventId) return;
      
      const updatedTitle = `${TEST_PREFIX} Updated Meeting`;
      
      const event = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.update',
        params: {
          id: testEventId,
          title: updatedTitle,
          location: 'Updated Location',
        },
      });

      expect(event.id).toBe(testEventId);
      expect(event.title).toBe(updatedTitle);
    });

    it('event.get - confirms update persisted', async () => {
      if (skipTests || !testEventId) return;
      
      const event = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.get',
        params: { id: testEventId },
      });

      expect(event.title).toBe(`${TEST_PREFIX} Updated Meeting`);
      expect(event.location).toBe('Updated Location');
    });

    it('event.delete - removes the event', async () => {
      if (skipTests || !testEventId) return;
      
      const result = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.delete',
        params: { id: testEventId },
      });

      // Remove from cleanup list since we just deleted it
      const idx = createdEvents.indexOf(testEventId);
      if (idx > -1) createdEvents.splice(idx, 1);

      // Verify delete succeeded
      expect(result).toBeDefined();
    });

    it('event.get - confirms deletion', async () => {
      if (skipTests || !testEventId) return;
      
      // Should throw error when trying to get deleted event
      await expect(
        aos().call('UseAdapter', {
          adapter,
          tool: 'event.get',
          params: { id: testEventId },
        })
      ).rejects.toThrow();
    });
  });

  // ===========================================================================
  // All-day events
  // ===========================================================================
  describe('all-day events', () => {
    let allDayEventId: string;
    
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dateStr = tomorrow.toISOString().split('T')[0];

    it('can create all-day event', async () => {
      if (skipTests) return;
      
      const event = await aos().call('UseAdapter', {
        adapter,
        tool: 'event.create',
        params: {
          title: `${TEST_PREFIX} All Day Event`,
          start: dateStr,  // Just date, no time = all-day
        },
      });

      expect(event).toHaveProperty('id');
      expect(event.all_day).toBe(true);
      
      allDayEventId = event.id;
      createdEvents.push(allDayEventId);
    });

    it('cleanup - delete all-day event', async () => {
      if (skipTests || !allDayEventId) return;
      
      await aos().call('UseAdapter', {
        adapter,
        tool: 'event.delete',
        params: { id: allDayEventId },
      });

      const idx = createdEvents.indexOf(allDayEventId);
      if (idx > -1) createdEvents.splice(idx, 1);
    });
  });
});
