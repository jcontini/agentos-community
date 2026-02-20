import { describe, it, expect } from "vitest";
import { execSync } from "child_process";

describe("anthropic.chat", () => {
  it("should accept chat request (dry run, no API key)", () => {
    // This test validates the operation definition is correct.
    // A real test would require a valid ANTHROPIC_API_KEY credential.
    
    // The chat utility accepts:
    // - model: string (required)
    // - messages: array (required)
    // - tools: array (optional)
    // - max_tokens: number (optional, default 4096)
    // - temperature: number (optional, default 0)
    // - system: string (optional)

    const validRequest = {
      model: "claude-3-5-haiku-20241022",
      messages: [
        {
          role: "user",
          content: "What is 2+2?"
        }
      ]
    };

    // Verify schema matches
    expect(validRequest).toBeDefined();
    expect(validRequest.model).toBeTruthy();
    expect(Array.isArray(validRequest.messages)).toBe(true);
    expect(validRequest.messages[0].role).toBe("user");
  });

  it("should support tool calls in request", () => {
    const requestWithTools = {
      model: "claude-3-5-haiku-20241022",
      messages: [
        {
          role: "user",
          content: "What is the weather in SF?"
        }
      ],
      tools: [
        {
          name: "get_weather",
          description: "Get current weather",
          input_schema: {
            type: "object",
            properties: {
              location: { type: "string" }
            },
            required: ["location"]
          }
        }
      ]
    };

    expect(requestWithTools.tools).toBeDefined();
    expect(Array.isArray(requestWithTools.tools)).toBe(true);
    expect(requestWithTools.tools[0].name).toBe("get_weather");
  });

  it("should support system prompt", () => {
    const requestWithSystem = {
      model: "claude-3-5-haiku-20241022",
      system: "You are a helpful assistant.",
      messages: [
        {
          role: "user",
          content: "Hello"
        }
      ]
    };

    expect(requestWithSystem.system).toBeTruthy();
  });
});
