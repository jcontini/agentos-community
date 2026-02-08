import { describe, it, expect, beforeAll } from "vitest";
import { aos } from "../../../tests/utils/fixtures";

const adapter = "whois";
let skipTests = false;

describe("WHOIS Adapter", () => {
  beforeAll(async () => {
    try {
      // whois has auth: none, but we still check if the system command exists
      await aos().call("UseAdapter", {
        adapter,
        tool: "domain.get",
        params: { domain: "example.com" },
      });
    } catch (e: any) {
      if (e.message?.includes("Credential not found") || e.message?.includes("Binary") || e.message?.includes("not found")) {
        console.log("  ⏭ Skipping WHOIS tests: whois command not available");
        skipTests = true;
      } else throw e;
    }
  });

  describe("domain.get", () => {
    it("returns whois data for a domain", async () => {
      if (skipTests) return;
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "domain.get",
        params: { domain: "google.com" },
      });
      expect(result).toBeDefined();
      expect(typeof result).toBe("string");
    });
  });

  describe("domain.check", () => {
    it("returns whois data for availability check", async () => {
      if (skipTests) return;
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "domain.check",
        params: { domain: "google.com" },
      });
      expect(result).toBeDefined();
      expect(typeof result).toBe("string");
    });
  });
});
