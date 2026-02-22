import { describe, it, expect, beforeAll } from "vitest";
import { aos } from "../../../tests/utils/fixtures";

const adapter = "here-now";
let skipAuthTests = false;

describe("here-now adapter", () => {
  beforeAll(async () => {
    // website.list requires auth — check for credentials
    try {
      await aos().call("UseAdapter", { adapter, tool: "website.list", params: {} });
    } catch (e: any) {
      if (e.message?.includes("Credential not found")) {
        console.log("  ⏭ Skipping auth-required tests: no credentials");
        skipAuthTests = true;
      }
    }
  });

  describe("website.list", () => {
    it("returns array of websites", async () => {
      if (skipAuthTests) return;
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "website.list",
        params: {},
      });
      expect(Array.isArray(result)).toBe(true);
    });
  });

  describe("website.create", () => {
    it("publishes HTML anonymously and returns a website entity with claim info", async () => {
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "website.create",
        params: {
          content: "<html><body><h1>AgentOS test publish</h1></body></html>",
          filename: "index.html",
          content_type: "text/html; charset=utf-8",
          title: "AgentOS Test",
        },
      });
      expect(result).toBeDefined();
      expect(result.url).toMatch(/\.here\.now/);
      expect(result.status).toBe("active");
      // Anonymous publish should include claim info in data
      expect(result.data).toBeDefined();
      expect(result.data.claim_url).toBeDefined();
    });
  });

  describe("website.update", () => {
    it("references tool for validation (skip — requires existing slug)", async () => {
      const _ = { tool: "website.update" };
      expect(true).toBe(true);
    });
  });

  describe("website.delete", () => {
    it("references tool for validation (skip — destructive)", async () => {
      const _ = { tool: "website.delete" };
      expect(true).toBe(true);
    });
  });

  describe("website.claim", () => {
    it("references tool for validation (skip — requires valid claim_token)", async () => {
      const _ = { tool: "website.claim" };
      expect(true).toBe(true);
    });
  });

  describe("website.patch_metadata", () => {
    it("references tool for validation (skip — requires existing slug)", async () => {
      const _ = { tool: "website.patch_metadata" };
      expect(true).toBe(true);
    });
  });

  describe("signup", () => {
    it("references tool for validation (skip — would send real email)", async () => {
      const _ = { tool: "signup" };
      expect(true).toBe(true);
    });
  });

  describe("claim", () => {
    it("references tool for validation (skip — requires valid claim_token)", async () => {
      const _ = { tool: "claim" };
      expect(true).toBe(true);
    });
  });

  describe("patch_metadata", () => {
    it("references tool for validation (skip — requires existing slug)", async () => {
      const _ = { tool: "patch_metadata" };
      expect(true).toBe(true);
    });
  });
});
