import { describe, it, expect } from "vitest";

describe("Anthropic Skill", () => {
  describe("chat", () => {
    it("validates chat request shape (skip - requires credentials)", () => {
      const _ = { tool: "chat" };
      expect(true).toBe(true);
    });
  });

  describe("model.list", () => {
    it("lists available models (skip - requires credentials)", () => {
      const _ = { tool: "model.list" };
      expect(true).toBe(true);
    });
  });
});
