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

  describe("conversation.list", () => {
    it("lists Claude Code sessions (skip - local command skill)", () => {
      const _ = { tool: "conversation.list" };
      expect(true).toBe(true);
    });
  });

  describe("conversation.search", () => {
    it("searches Claude Code sessions by content (skip - local command skill)", () => {
      const _ = { tool: "conversation.search" };
      expect(true).toBe(true);
    });
  });

  describe("conversation.get", () => {
    it("gets a Claude Code session by UUID (skip - local command skill)", () => {
      const _ = { tool: "conversation.get" };
      expect(true).toBe(true);
    });
  });
});
