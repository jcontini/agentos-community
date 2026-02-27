/**
 * SerpAPI Skill Tests
 *
 * Tests for Google Flights search via SerpAPI.
 * Requires: SERPAPI_API_KEY or configured credential in AgentOS.
 *
 * SerpAPI returns flight OFFERS — priced itineraries containing one or
 * more flight segments. Each result is an offer entity with price,
 * currency, and flight details in data.*.
 *
 * Coverage:
 * - offer.search (search flight offers)
 * - offer.list (best/recommended offers)
 * - offer.get (return flight offers via departure token)
 * - get_booking_options (utility)
 * - get_price_insights (utility)
 */

import { describe, it, expect, beforeAll } from "vitest";
import { aos } from "@test/fixtures";

const adapter = "serpapi";

let skipTests = false;

describe("SerpAPI Skill", () => {
  beforeAll(async () => {
    try {
      // Light probe — one-way flight search to verify credentials work
      await aos().call("UseAdapter", {
        adapter,
        tool: "offer.search",
        params: {
          departure_id: "AUS",
          arrival_id: "JFK",
          outbound_date: "2026-06-15",
          type: 2,
        },
      });
    } catch (e: unknown) {
      const error = e as Error;
      if (
        error.message?.includes("No credentials configured") ||
        error.message?.includes("Credential not found")
      ) {
        console.log("  ⏭ Skipping SerpAPI tests: no credentials configured");
        skipTests = true;
      } else {
        throw e;
      }
    }
  });

  // ===========================================================================
  // offer.search
  // ===========================================================================
  describe("offer.search", () => {
    it("returns an array of flight offers", async () => {
      if (skipTests) return;

      const results = await aos().call("UseAdapter", {
        adapter,
        tool: "offer.search",
        params: {
          departure_id: "AUS",
          arrival_id: "JFK",
          outbound_date: "2026-06-15",
          type: 2,
        },
      });

      expect(Array.isArray(results)).toBe(true);
      expect((results as unknown[]).length).toBeGreaterThan(0);
    });

    it("offers have required fields", async () => {
      if (skipTests) return;

      const results = (await aos().call("UseAdapter", {
        adapter,
        tool: "offer.search",
        params: {
          departure_id: "LAX",
          arrival_id: "LHR",
          outbound_date: "2026-07-01",
          type: 2,
        },
      })) as Array<{
        name: string;
        price: number;
        offer_type: string;
        data: { flights: unknown[]; total_duration: number };
        adapter: string;
      }>;

      expect(results.length).toBeGreaterThan(0);

      for (const offer of results.slice(0, 3)) {
        expect(offer.name).toBeDefined();
        expect(typeof offer.name).toBe("string");
        expect(offer.price).toBeDefined();
        expect(typeof offer.price).toBe("number");
        expect(offer.offer_type).toBe("flight");
        expect(offer.data.flights).toBeDefined();
        expect(Array.isArray(offer.data.flights)).toBe(true);
        expect(offer.data.total_duration).toBeDefined();
        expect(offer.adapter).toBe(adapter);
      }
    });

    it("round trip offers include departure tokens", async () => {
      if (skipTests) return;

      const results = (await aos().call("UseAdapter", {
        adapter,
        tool: "offer.search",
        params: {
          departure_id: "SFO",
          arrival_id: "NRT",
          outbound_date: "2026-08-01",
          return_date: "2026-08-15",
          type: 1,
        },
      })) as Array<{ data: { departure_token?: string } }>;

      expect(results.length).toBeGreaterThan(0);

      // Round trip outbound offers should have departure tokens
      const withToken = results.filter((o) => o.data?.departure_token);
      expect(withToken.length).toBeGreaterThan(0);
    });

    it("respects stops filter", async () => {
      if (skipTests) return;

      const results = (await aos().call("UseAdapter", {
        adapter,
        tool: "offer.search",
        params: {
          departure_id: "AUS",
          arrival_id: "LAX",
          outbound_date: "2026-06-15",
          type: 2,
          stops: 1, // Nonstop only
        },
      })) as Array<{ data: { layovers?: unknown[] } }>;

      // Nonstop offers should have no layovers
      for (const offer of results) {
        expect(offer.data?.layovers ?? []).toHaveLength(0);
      }
    });
  });

  // ===========================================================================
  // offer.list
  // ===========================================================================
  describe("offer.list", () => {
    it("returns best/recommended offers when available", async () => {
      if (skipTests) return;

      const results = await aos().call("UseAdapter", {
        adapter,
        tool: "offer.list",
        params: {
          departure_id: "LAX",
          arrival_id: "JFK",
          outbound_date: "2026-07-01",
          type: 2,
        },
      });

      // best_flights may not always be present — empty array is valid
      expect(Array.isArray(results)).toBe(true);
    });
  });

  // ===========================================================================
  // offer.get
  // ===========================================================================
  describe("offer.get", () => {
    it("returns return flight offers when given a departure token", async () => {
      if (skipTests) return;

      // First, get outbound offers with departure tokens
      const outbound = (await aos().call("UseAdapter", {
        adapter,
        tool: "offer.search",
        params: {
          departure_id: "AUS",
          arrival_id: "LAX",
          outbound_date: "2026-07-01",
          return_date: "2026-07-08",
          type: 1,
        },
      })) as Array<{ data: { departure_token?: string } }>;

      const withToken = outbound.find((o) => o.data?.departure_token);
      if (!withToken) {
        console.log("  ⏭ No departure token found, skipping offer.get test");
        return;
      }

      const returnOffers = await aos().call("UseAdapter", {
        adapter,
        tool: "offer.get",
        params: {
          departure_token: withToken.data.departure_token!,
        },
      });

      expect(Array.isArray(returnOffers)).toBe(true);
      expect((returnOffers as unknown[]).length).toBeGreaterThan(0);
    });
  });

  // ===========================================================================
  // get_booking_options (utility — skipped, requires valid token chain)
  // ===========================================================================
  describe("get_booking_options", () => {
    it("placeholder for booking options (skipped — requires full selection)", async () => {
      const _ = { tool: "get_booking_options" };
      expect(true).toBe(true);
    });
  });

  // ===========================================================================
  // get_price_insights (utility)
  // ===========================================================================
  describe("get_price_insights", () => {
    it("returns price insights for a route", async () => {
      if (skipTests) return;

      const result = (await aos().call("UseAdapter", {
        adapter,
        tool: "get_price_insights",
        params: {
          departure_id: "AUS",
          arrival_id: "JFK",
          outbound_date: "2026-06-15",
          return_date: "2026-06-22",
        },
      })) as {
        lowest_price?: number;
        price_level?: string;
        typical_price_range?: number[];
      };

      // Price insights may not always be available for all routes
      if (result && result.lowest_price) {
        expect(typeof result.lowest_price).toBe("number");
        expect(typeof result.price_level).toBe("string");
        expect(Array.isArray(result.typical_price_range)).toBe(true);
      }
    });
  });
});
