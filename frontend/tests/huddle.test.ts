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
    await expect(live.create(EXAMPLE_QUESTION)).rejects.toThrow("question format");
  });
  it("runs the live question, evidence, match, and huddle sequence through /api routes", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "live");
    vi.resetModules();
    const question = { question_id: "q-1", specialty: "Oncology", condition: "Breast Cancer", topic: "Treatment Sequencing", intent: "Treatment Options", question: EXAMPLE_QUESTION, key_context: [], extraction_method: "rules", confidence: 0.9, phi_detected: false };
    const source = { id: "PMID1", title: "Corpus source", type: "Article", date: null, snippet: "Verbatim source snippet.", url: null, citation: "Corpus citation", relevance: 0.7, verified: false, source_type: "Article", publisher: "PubMed", specialty: "Oncology", condition: "Breast Cancer", topics: ["Treatment Sequencing"], external_id: "PMID1" };
    const expert = { id: "demo-expert-1", name: "Synthetic Expert", title: "Demo profile", specialty: "Oncology", expertise: ["Breast Cancer"], match_score: 80, availability: "available", score_breakdown: { specialty: 35 }, is_demo: true };
    const detail = { huddle: { id: "h-1", question_id: "q-1", expert_id: expert.id, evidence_ids: ["PMID1"], status: "awaiting_expert", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }, question, evidence: [source], expert, responses: [], brief: null, disclaimer: "Synthetic" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(question), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ question_id: "q-1", retrieval_method: "bm25", sources: [source] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ experts: [expert], disclaimer: "Synthetic", score_note: "Relevance" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(detail), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const { huddleApi: live } = await import("../lib/api");
    const huddle = await live.create(EXAMPLE_QUESTION);
    expect(huddle.id).toBe("h-1");
    expect(huddle.demo).toBe(false);
    expect(huddle.status).toBe("ready");
    expect(huddle.sources[0].url).toBeNull();
    expect(huddle.expert?.match).toBe(80);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8000/api/questions",
      "http://localhost:8000/api/evidence/q-1",
      "http://localhost:8000/api/experts/match/q-1",
      "http://localhost:8000/api/huddles",
    ]);
    expect(JSON.parse(String(fetchMock.mock.calls[3][1]?.body))).toEqual({ question_id: "q-1", expert_id: expert.id, evidence_ids: ["PMID1"] });
  });
});
