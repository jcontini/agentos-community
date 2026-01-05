/**
 * Goodreads Connector Tests
 * 
 * Tests for Goodreads CSV pull functionality.
 * Uses fixture files in the fixtures/ directory.
 */

import { describe, it, expect, afterAll } from 'vitest';
import { aos, cleanupTestData } from '../../../tests/utils/fixtures';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const fixturesDir = join(__dirname, 'fixtures');

describe('Goodreads Connector', () => {
  // Clean up any pulled test data
  afterAll(async () => {
    const deleted = await cleanupTestData('Books', 
      (book) => book.refs?.goodreads && book.title?.startsWith('[TEST]')
    );
    if (deleted > 0) {
      console.log(`  Cleaned up ${deleted} pulled test books`);
    }
  });

  describe('CSV Pull', () => {
    it('pulls books from CSV (dry run)', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      
      const result = await aos().books.pull('goodreads', csvPath, true);

      expect(result).toBeDefined();
      expect(result.pulled).toBeGreaterThan(0);
      expect(result.errors).toEqual([]);
    });

    it('actually pulls books from CSV', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      
      // Pull for real
      const result = await aos().books.pull('goodreads', csvPath, false);
      // On re-run, might be 0 (already pulled) due to UNIQUE constraint
      expect(result.pulled).toBeGreaterThanOrEqual(0);
      expect(result.errors).toEqual([]);

      // Verify books exist (either just pulled or previously pulled)
      const books = await aos().books.list({ limit: 100 });
      const pulledBook = books.find(b => b.refs?.goodreads === '12345');
      
      expect(pulledBook).toBeDefined();
      expect(pulledBook.refs?.goodreads).toBe('12345');
    });
  });

  describe('Field Mapping', () => {
    it('maps title correctly', async () => {
      const csvPath = join(fixturesDir, 'sample-export.csv');
      await aos().books.pull('goodreads', csvPath, false);

      const books = await aos().books.list();
      const book = books.find(b => b.refs?.goodreads === '12345');

      expect(book?.title).toBe('[TEST] The Great Gatsby');
    });

    it('maps authors correctly', async () => {
      const books = await aos().books.list();
      const book = books.find(b => b.refs?.goodreads === '12345');

      expect(book?.authors).toBeDefined();
      expect(Array.isArray(book?.authors)).toBe(true);
      expect(book?.authors).toContain('F. Scott Fitzgerald');
    });

    it('strips ISBN quotes wrapper', async () => {
      const books = await aos().books.list();
      const book = books.find(b => b.refs?.goodreads === '12345');

      // Goodreads CSVs have ISBNs like ="0743273567"
      // Should be stripped to just the number
      expect(book?.refs?.isbn).toBe('0743273567');
      expect(book?.refs?.isbn).not.toContain('=');
      expect(book?.refs?.isbn).not.toContain('"');
    });

    it('maps exclusive shelf to status', async () => {
      const books = await aos().books.list();
      
      // Check different shelf mappings from fixture
      const readBook = books.find(b => b.refs?.goodreads === '12345');
      const readingBook = books.find(b => b.refs?.goodreads === '12346');
      const toReadBook = books.find(b => b.refs?.goodreads === '12347');

      expect(readBook?.status).toBe('read');
      expect(readingBook?.status).toBe('reading');
      expect(toReadBook?.status).toBe('want_to_read');
    });

    it('maps rating correctly (0 = null)', async () => {
      const books = await aos().books.list();
      
      const ratedBook = books.find(b => b.refs?.goodreads === '12345');
      const unratedBook = books.find(b => b.refs?.goodreads === '12347');

      expect(ratedBook?.rating).toBe(5);
      expect(unratedBook?.rating).toBeNull();
    });
  });

  describe('Edge Cases', () => {
    it('handles empty CSV gracefully', async () => {
      const csvPath = join(fixturesDir, 'empty.csv');
      
      const result = await aos().books.pull('goodreads', csvPath, true);

      expect(result.pulled).toBe(0);
      expect(result.errors).toEqual([]);
    });

    it('reports errors for rows with missing title', async () => {
      const csvPath = join(fixturesDir, 'missing-fields.csv');
      
      const result = await aos().books.pull('goodreads', csvPath, true);

      // File has 2 rows - one missing title (should error), one valid
      expect(result).toBeDefined();
      // Should report the error for the row with missing title
      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.errors[0].error).toContain('Missing title');
    });
  });
});
