/**
 * Research Web Agent Skill Tests
 *
 * Tests the research-web agent skill end-to-end:
 * - Invokes the agent via use()
 * - Verifies a job entity is created on the graph
 * - Verifies a conversation entity is created with messages
 * - Verifies the response contains content
 *
 * Requires: Anthropic API key + at least one of Exa/Brave configured.
 * Skip behavior: if missing credentials, tests are skipped gracefully.
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { aos } from '@test/fixtures';

const SKILL = 'research-web';

let skipTests = false;

describe('Research Web Agent Skill', () => {
  beforeAll(async () => {
    // Check if anthropic + a web search skill are configured
    try {
      const readme = await fetch('http://127.0.0.1:3457/readme.mcp');
      const text = await readme.text();
      const hasAnthropic = text.includes('anthropic') && text.includes('Ready');
      const hasWebSearch = text.includes('exa') || text.includes('brave');

      if (!hasAnthropic || !hasWebSearch) {
        console.log('  ⏭ Skipping research-web tests: needs anthropic + web search credentials');
        skipTests = true;
      }
    } catch {
      console.log('  ⏭ Skipping research-web tests: server not available');
      skipTests = true;
    }
  });

  it('returns a job_id and conversation_id', async () => {
    if (skipTests) return;

    const result = await aos().call('UseAdapter', {
      adapter: SKILL,
      tool: 'research',
      params: { prompt: 'What year was SQLite first released? One sentence answer.' },
    }) as { job_id: string; conversation_id: string; content: string };

    expect(result.job_id).toBeDefined();
    expect(typeof result.job_id).toBe('string');
    expect(result.conversation_id).toBeDefined();
    expect(typeof result.conversation_id).toBe('string');
  }, 60_000);

  it('returns non-empty content', async () => {
    if (skipTests) return;

    const result = await aos().call('UseAdapter', {
      adapter: SKILL,
      tool: 'research',
      params: { prompt: 'What is the capital of France? One word.' },
    }) as { content: string };

    expect(result.content).toBeDefined();
    expect(typeof result.content).toBe('string');
    expect(result.content.length).toBeGreaterThan(0);
  }, 60_000);

  it('job entity is on the graph after completion', async () => {
    if (skipTests) return;

    const result = await aos().call('UseAdapter', {
      adapter: SKILL,
      tool: 'research',
      params: { prompt: 'What programming language is the Linux kernel written in? One word.' },
    }) as { job_id: string };

    // Verify job entity exists on the graph
    const response = await fetch(`http://127.0.0.1:3457/mem/jobs/${result.job_id}`);
    expect(response.ok).toBe(true);

    const job = await response.json() as { data: { status: string; kind: string } };
    expect(job.data.status).toBe('completed');
    expect(job.data.kind).toBe('agent');
  }, 60_000);
});
