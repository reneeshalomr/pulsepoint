import { describe, it, expect, vi, afterEach } from "vitest";
import {
  makeHuddle,
  completeHuddle,
  EXAMPLE_QUESTION,
  EXAMPLE_RESPONSE,
} from "../data/demo";
import { HuddleSchema } from "../types/huddle";
import { huddleApi } from "../lib/api";
describe("demo huddle lifecycle", () => {
  it("preserves the question, separates expert opinion, and produces a labeled brief", async () => {
    const h = await huddleApi.create(EXAMPLE_QUESTION);
    expect(h.question.question).toBe(EXAMPLE_QUESTION);
    expect(h.status).toBe("ready");
    expect(h.expert?.demo).toBe(true);
    const requested = await huddleApi.requestExpert(h);
    expect(requested.status).toBe("pending");
    const complete = await huddleApi.respond(requested, EXAMPLE_RESPONSE);
    expect(complete.status).toBe("complete");
    expect(complete.response).toBe(EXAMPLE_RESPONSE);
    expect(complete.brief?.synthesisLabel).toContain("demo");
    expect(HuddleSchema.safeParse(complete).success).toBe(true);
  });
  it("does not invent evidence or experts for an unsupported question", () => {
    const h = makeHuddle("How do I review arrhythmia evidence?");
    expect(h.sources).toHaveLength(0);
    expect(h.expert).toBeNull();
    expect(h.question.specialty).toBe("Needs review");
  });
  it("rejects blank, oversized, and too-short submissions", async () => {
    await expect(huddleApi.create("  ")).rejects.toThrow();
    await expect(huddleApi.create("x".repeat(2001))).rejects.toThrow();
    await expect(
      huddleApi.respond(makeHuddle(EXAMPLE_QUESTION), "short"),
    ).rejects.toThrow();
  });
  it("does not overwrite the original huddle when creating a brief", () => {
    const h = makeHuddle(EXAMPLE_QUESTION);
    completeHuddle(h, EXAMPLE_RESPONSE);
    expect(h.status).toBe("ready");
    expect(h.response).toBeNull();
  });
});
describe("live adapter failures", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });
  it("surfaces backend errors without silently replacing them with demo results", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "live");
    vi.resetModules();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("Service unavailable", { status: 503 }),
        ),
    );
    const { huddleApi: live } = await import("../lib/api");
    await expect(live.create(EXAMPLE_QUESTION)).rejects.toThrow("503");
    expect((await live.create(EXAMPLE_QUESTION, true)).demo).toBe(true);
  });
  it("rejects malformed service responses", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "live");
    vi.resetModules();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ answer: "unstructured" }), {
            status: 200,
          }),
        ),
    );
    const { huddleApi: live } = await import("../lib/api");
    await expect(live.create(EXAMPLE_QUESTION)).rejects.toThrow("format");
  });
});
