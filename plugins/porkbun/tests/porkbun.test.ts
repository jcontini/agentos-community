import { describe, test, expect, beforeAll, afterAll } from "vitest";
import { aos, testContent } from "../../../tests/utils/fixtures";

describe("porkbun", () => {
  let skipTests = false;
  const createdItems: { id: string; domain: string }[] = [];

  beforeAll(async () => {
    // Check if credentials are configured
    const result = await aos("porkbun", "domain.list", {});
    if (result.status === 401 || result.error?.includes("Credential not found")) {
      skipTests = true;
      console.log("Skipping porkbun tests: no credentials configured");
    }
  });

  afterAll(async () => {
    // Cleanup created DNS records
    for (const item of createdItems) {
      try {
        await aos("porkbun", "dns_record.delete", { domain: item.domain, id: item.id });
      } catch {
        // Ignore cleanup errors
      }
    }
  });

  test("domain.list", async () => {
    if (skipTests) return;
    const result = await aos("porkbun", "domain.list", {});
    expect(result.status).toBe(200);
    expect(result.data).toBeDefined();
    expect(Array.isArray(result.data)).toBe(true);
  });

  test("domain.get", async () => {
    if (skipTests) return;
    // First get a domain from the list
    const listResult = await aos("porkbun", "domain.list", {});
    if (!listResult.data || listResult.data.length === 0) {
      console.log("Skipping domain.get: no domains in account");
      return;
    }
    const domain = listResult.data[0].fqdn;
    
    const result = await aos("porkbun", "domain.get", { domain });
    expect(result.status).toBe(200);
    expect(result.data).toBeDefined();
  });

  test("dns_record.list", async () => {
    if (skipTests) return;
    // First get a domain from the list
    const listResult = await aos("porkbun", "domain.list", {});
    if (!listResult.data || listResult.data.length === 0) {
      console.log("Skipping dns_record.list: no domains in account");
      return;
    }
    const domain = listResult.data[0].fqdn;
    
    const result = await aos("porkbun", "dns_record.list", { domain });
    expect(result.status).toBe(200);
    expect(result.data).toBeDefined();
    expect(Array.isArray(result.data)).toBe(true);
  });

  test("dns_record.create", async () => {
    if (skipTests) return;
    // First get a domain from the list
    const listResult = await aos("porkbun", "domain.list", {});
    if (!listResult.data || listResult.data.length === 0) {
      console.log("Skipping dns_record.create: no domains in account");
      return;
    }
    const domain = listResult.data[0].fqdn;
    const uniqueName = testContent("agentos-test");
    
    const result = await aos("porkbun", "dns_record.create", {
      domain,
      name: uniqueName,
      type: "TXT",
      content: "agentos-test-record",
      ttl: 600
    });
    
    expect(result.status).toBe(200);
    expect(result.data).toBeDefined();
    
    // Track for cleanup
    if (result.data?.id) {
      createdItems.push({ id: result.data.id, domain });
    }
  });

  test("dns_record.update", async () => {
    if (skipTests) return;
    // This test requires a record to exist - skip if no created items
    if (createdItems.length === 0) {
      console.log("Skipping dns_record.update: no records created");
      return;
    }
    
    const { id, domain } = createdItems[0];
    const result = await aos("porkbun", "dns_record.update", {
      domain,
      id,
      name: testContent("agentos-test"),
      type: "TXT",
      content: "agentos-test-record-updated",
      ttl: 600
    });
    
    expect(result.status).toBe(200);
    expect(result.data).toBeDefined();
  });

  test("dns_record.delete", async () => {
    if (skipTests) return;
    // This test requires a record to exist - skip if no created items
    if (createdItems.length === 0) {
      console.log("Skipping dns_record.delete: no records created");
      return;
    }
    
    const { id, domain } = createdItems.pop()!;
    const result = await aos("porkbun", "dns_record.delete", { domain, id });
    
    expect(result.status).toBe(200);
    expect(result.data).toBeDefined();
  });
});
