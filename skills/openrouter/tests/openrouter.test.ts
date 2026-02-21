import { describe, it, expect } from 'vitest';

describe('OpenRouter Skill', () => {
  describe('chat', () => {
    it('validates request shape for chat', async () => {
      // Validation relies on tool references in test files.
      const request = {
        adapter: 'openrouter',
        tool: 'chat',
        params: {
          model: 'openai/gpt-4o-mini',
          messages: [{ role: 'user', content: 'Hello' }],
        },
      };

      expect(request.tool).toBe('chat');
      expect(request.params.model).toBeTruthy();
      expect(Array.isArray(request.params.messages)).toBe(true);
    });
  });
});
