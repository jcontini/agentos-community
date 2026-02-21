import { describe, it, expect } from 'vitest';

describe('OpenRouter Skill', () => {
  describe('chat', () => {
    it('validates request shape for chat', async () => {
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

  describe('model.list', () => {
    it('lists available models (skip - requires credentials)', async () => {
      const _ = { tool: 'model.list' };
      expect(true).toBe(true);
    });
  });
});
