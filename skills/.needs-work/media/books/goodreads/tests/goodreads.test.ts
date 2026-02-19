/**
 * Goodreads Adapter Tests
 * 
 * Tests CSV parsing and field mapping.
 */

import { describe, it, expect } from 'vitest';
import { aos } from '@test/fixtures';
import { join } from 'path';

const fixturesDir = join(__dirname, 'fixtures');

describe('Goodreads Adapter', () => {
  describe('CSV Import', () => {
    it('parses CSV and returns records', async () => {
      const csvPath = join(fixturesDir, 'sample.csv');
      
      const result = await aos().call('UseAdapter', {
        adapter: 'goodreads',
        tool: 'pull',
        params: { path: csvPath },
        execute: true
      });

      expect(result).toBeDefined();
      expect(Array.isArray(result.records || result)).toBe(true);
    });

    it('maps title correctly', async () => {
      const csvPath = join(fixturesDir, 'sample.csv');
      
      const result = await aos().call('UseAdapter', {
        adapter: 'goodreads',
        tool: 'pull',
        params: { path: csvPath },
        execute: true
      });

      const records = result.records || result;
      const book = records.find((b: any) => b.goodreads_id === '12345');
      
      expect(book).toBeDefined();
      expect(book.title).toBe('[TEST] The Great Gatsby');
    });

    it('maps status from Exclusive Shelf', async () => {
      const csvPath = join(fixturesDir, 'sample.csv');
      
      const result = await aos().call('UseAdapter', {
        adapter: 'goodreads',
        tool: 'pull',
        params: { path: csvPath },
        execute: true
      });

      const records = result.records || result;
      
      const readBook = records.find((b: any) => b.goodreads_id === '12345');
      const readingBook = records.find((b: any) => b.goodreads_id === '12346');
      const toReadBook = records.find((b: any) => b.goodreads_id === '12347');

      expect(readBook?.status).toBe('read');
      expect(readingBook?.status).toBe('reading');
      expect(toReadBook?.status).toBe('want_to_read');
    });

    it('strips ISBN wrapper quotes', async () => {
      const csvPath = join(fixturesDir, 'sample.csv');
      
      const result = await aos().call('UseAdapter', {
        adapter: 'goodreads',
        tool: 'pull',
        params: { path: csvPath },
        execute: true
      });

      const records = result.records || result;
      const book = records.find((b: any) => b.goodreads_id === '12345');

      // Goodreads exports ISBNs like ="0743273567" - should be stripped
      expect(book?.isbn).toBe('0743273567');
      expect(book?.isbn).not.toContain('=');
      expect(book?.isbn).not.toContain('"');
    });

    it('maps rating (0 becomes null or 0)', async () => {
      const csvPath = join(fixturesDir, 'sample.csv');
      
      const result = await aos().call('UseAdapter', {
        adapter: 'goodreads',
        tool: 'pull',
        params: { path: csvPath },
        execute: true
      });

      const records = result.records || result;
      const ratedBook = records.find((b: any) => b.goodreads_id === '12345');
      const unratedBook = records.find((b: any) => b.goodreads_id === '12346');

      expect(ratedBook?.rating).toBe(5);
      // Unrated books have rating 0 in CSV - may be 0 or null depending on transform
      expect([0, null]).toContain(unratedBook?.rating);
    });
  });
});
