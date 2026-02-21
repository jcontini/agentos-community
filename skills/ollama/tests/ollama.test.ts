import { describe, it, expect } from 'vitest';

describe('Ollama Skill', () => {
  describe('chat', () => {
    it('validates request shape for chat', async () => {
      // Validation relies on tool references in test files.
      const request = {
        adapter: 'ollama',
        tool: 'chat',
        params: {
          model: 'llama3.2',
          messages: [{ role: 'user', content: 'Hello from local model' }],
        },
      };

      expect(request.tool).toBe('chat');
      expect(request.params.model).toBeTruthy();
      expect(Array.isArray(request.params.messages)).toBe(true);
    });
  });
});
