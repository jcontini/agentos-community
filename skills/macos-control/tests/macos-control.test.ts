import { describe, it, expect } from "vitest";
import { aos } from "@test/fixtures";

const adapter = "macos-control";

describe("macOS Control Skill", () => {
  describe("list_apps", () => {
    it("lists installed applications", async () => {
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "list_apps",
        params: { limit: 5 },
      }) as { apps: Array<{ name?: string; path?: string }>; count: number };

      expect(Array.isArray(result.apps)).toBe(true);
      expect(typeof result.count).toBe("number");
      expect(result.apps.length).toBeGreaterThan(0);
      expect(result.apps[0].name).toBeDefined();
      expect(result.apps[0].path).toContain(".app");
    });
  });

  describe("list_processes", () => {
    it("lists running processes", async () => {
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "list_processes",
        params: { limit: 5 },
      }) as { processes: Array<{ pid?: number; command?: string }>; count: number };

      expect(Array.isArray(result.processes)).toBe(true);
      expect(typeof result.count).toBe("number");
      expect(result.processes.length).toBeGreaterThan(0);
      expect(result.processes[0].pid).toBeDefined();
      expect(result.processes[0].command).toBeDefined();
    });
  });

  describe("list_displays", () => {
    it("lists displays with geometry", async () => {
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "list_displays",
        params: {},
      }) as { displays: Array<{ display_id?: string; frame?: { width?: number } }>; count: number };

      expect(Array.isArray(result.displays)).toBe(true);
      expect(typeof result.count).toBe("number");
      expect(result.displays.length).toBeGreaterThan(0);
      expect(result.displays[0].display_id).toBeDefined();
      expect(result.displays[0].frame?.width).toBeGreaterThan(0);
    });
  });

  describe("list_windows", () => {
    it("lists user-facing windows", async () => {
      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "list_windows",
        params: { limit: 10 },
      }) as { windows: Array<{ app_name?: string; capture_eligible?: boolean }>; count: number };

      expect(Array.isArray(result.windows)).toBe(true);
      expect(typeof result.count).toBe("number");
      expect(result.windows.length).toBeGreaterThan(0);
      expect(result.windows[0].app_name).toBeDefined();
      expect(typeof result.windows[0].capture_eligible).toBe("boolean");
    });
  });

  describe("screenshot_display", () => {
    it("captures a display screenshot", async () => {
      const displays = await aos().call("UseAdapter", {
        adapter,
        tool: "list_displays",
        params: {},
      }) as { displays: Array<{ display_index?: number }> };

      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "screenshot_display",
        params: {
          display_index: displays.displays[0]?.display_index,
          path: "/tmp/macos-control-test-display.png",
        },
      }) as { path?: string; display_index?: number };

      expect(result.display_index).toBeDefined();
      expect(result.path).toContain("macos-control-test-display.png");
    });
  });

  describe("screenshot_window", () => {
    it("captures a window screenshot when an eligible window exists", async () => {
      const windows = await aos().call("UseAdapter", {
        adapter,
        tool: "list_windows",
        params: { limit: 20 },
      }) as { windows: Array<{ window_id?: number; capture_eligible?: boolean }> };

      const target = windows.windows.find((window) => window.capture_eligible && window.window_id);
      expect(target).toBeDefined();

      const result = await aos().call("UseAdapter", {
        adapter,
        tool: "screenshot_window",
        params: {
          window_id: target?.window_id,
          path: "/tmp/macos-control-test-window.png",
        },
      }) as { path?: string; window_id?: number };

      expect(result.window_id).toBe(target?.window_id);
      expect(result.path).toContain("macos-control-test-window.png");
    });
  });
});
