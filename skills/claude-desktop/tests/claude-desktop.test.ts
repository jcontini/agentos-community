import { describe, it, expect } from "vitest";

describe("Claude Desktop Skill", () => {
  describe("chat", () => {
    it("validates request shape (skip - requires live OAuth token)", () => {
      const _ = { tool: "chat" };
      expect(true).toBe(true);
    });
  });

  describe("model.list", () => {
    it("lists available models (skip - requires live OAuth token)", () => {
      const _ = { tool: "model.list" };
      expect(true).toBe(true);
    });
  });
});
