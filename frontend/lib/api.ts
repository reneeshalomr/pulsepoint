import { makeHuddle, completeHuddle, EXAMPLE_RESPONSE } from "../data/demo";
import { mapHuddleDetail, type AnalyticsDTO, type BriefDTO, type EvidenceDTO, type ExpertDTO, type Huddle, type HuddleDetailDTO, type QuestionDTO } from "../types/huddle";

export const isLive = process.env.NEXT_PUBLIC_API_MODE === "live";
const baseUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, method: "GET" | "POST" = "GET", body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const result = await fetch(`${baseUrl}/api${path}`, { method, headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal });
    if (!result.ok) {
      let detail = "";
      try { const payload = await result.json(); detail = typeof payload.detail === "string" ? ` ${payload.detail}` : ""; } catch { /* Keep errors concise. */ }
      throw new Error(`The service returned ${result.status}.${detail} Please retry or switch to the demo.`);
    }
    return await result.json() as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw new Error("The service took too long. Please retry or switch to the demo.");
    throw error;
  } finally { clearTimeout(timer); }
}

export const backendApi = {
  async createQuestion(text: string): Promise<QuestionDTO> {
    const value = await request<unknown>("/questions", "POST", { text });
    if (!value || typeof value !== "object" || typeof (value as Record<string, unknown>).question_id !== "string" || typeof (value as Record<string, unknown>).question !== "string") {
      throw new Error("The service response does not match the agreed question format.");
    }
    return value as QuestionDTO;
  },
  getEvidence: (id: string) => request<{ question_id: string; retrieval_method: string; sources: EvidenceDTO[] }>(`/evidence/${encodeURIComponent(id)}`),
  getExpertMatches: (id: string) => request<{ experts: ExpertDTO[]; disclaimer: string; score_note: string }>(`/experts/match/${encodeURIComponent(id)}`),
  createHuddle: (question_id: string, expert_id: string, evidence_ids: string[]) => request<HuddleDetailDTO>("/huddles", "POST", { question_id, expert_id, evidence_ids }),
  getHuddle: (id: string) => request<HuddleDetailDTO>(`/huddles/${encodeURIComponent(id)}`),
  getHuddles: () => request<{ huddles: HuddleDetailDTO[]; disclaimer: string }>("/huddles"),
  simulateResponse: (id: string) => request<{ huddle_id: string; status: string; response: { text: string; is_simulated: boolean } }>(`/huddles/${encodeURIComponent(id)}/simulate-response`, "POST"),
  submitResponse: (id: string, expert_id: string, mode: "text" | "voice", text: string, optional: { transcript?: string; audio_url?: string; duration_seconds?: number } = {}) => request<{ huddle_id: string; status: string; response: { text: string; is_simulated: boolean } }>(`/huddles/${encodeURIComponent(id)}/response`, "POST", { expert_id, mode, text, ...optional }),
  synthesizeHuddle: (id: string) => request<{ huddle_id: string; status: string; brief: BriefDTO }>(`/huddles/${encodeURIComponent(id)}/synthesize`, "POST"),
  getAnalytics: (days = 30, specialty?: string) => request<AnalyticsDTO>(`/analytics/questions?${new URLSearchParams({ days: String(days), ...(specialty ? { specialty } : {}) })}`),
  getHealth: () => request<{ status: string; db: string; llm_provider: string; corpus_size: number; experts_count: number }>("/health"),
};

export const huddleApi = {
  async create(question: string, forceDemo = false): Promise<Huddle> {
    if (!question.trim() || question.length > 2000) throw new Error("Enter a question between 1 and 2,000 characters.");
    if (isLive && !forceDemo) {
      const created = await backendApi.createQuestion(question.trim());
      const [evidence, matches] = await Promise.all([backendApi.getEvidence(created.question_id), backendApi.getExpertMatches(created.question_id)]);
      const expert = matches.experts[0];
      if (!expert) throw new Error("The backend did not return an expert match for this question.");
      const detail = await backendApi.createHuddle(created.question_id, expert.id, evidence.sources.map((source) => source.id));
      return mapHuddleDetail({ ...detail, question: created, evidence: evidence.sources, expert });
    }
    return makeHuddle(question.trim(), `demo-${crypto.randomUUID()}`);
  },
  async requestExpert(huddle: Huddle): Promise<Huddle> {
    if (huddle.demo) return { ...huddle, status: "pending" };
    const refreshed = mapHuddleDetail(await backendApi.getHuddle(huddle.id));
    return { ...refreshed, status: refreshed.status === "ready" ? "pending" : refreshed.status };
  },
  async simulate(huddle: Huddle): Promise<Huddle> {
    if (huddle.demo) return completeHuddle(huddle, EXAMPLE_RESPONSE);
    let detail = await backendApi.getHuddle(huddle.id);
    if (detail.huddle.status === "awaiting_expert") {
      await backendApi.simulateResponse(huddle.id);
      detail = await backendApi.getHuddle(huddle.id);
    }
    if (detail.huddle.status !== "synthesized") {
      const synthesized = await backendApi.synthesizeHuddle(huddle.id);
      return mapHuddleDetail(detail, synthesized.brief);
    }
    return mapHuddleDetail(detail);
  },
  async respond(huddle: Huddle, response: string, mode: "text" | "voice" = "text"): Promise<Huddle> {
    if (response.trim().length < 20 || response.length > 4000) throw new Error("Please enter a response between 20 and 4,000 characters.");
    if (huddle.demo) return completeHuddle(huddle, response.trim());
    if (!huddle.expert) throw new Error("The huddle has no matched expert profile.");
    let detail = await backendApi.getHuddle(huddle.id);
    if (detail.huddle.status === "awaiting_expert") {
      await backendApi.submitResponse(huddle.id, huddle.expert.id, mode, response.trim(), mode === "voice" ? { transcript: response.trim() } : {});
      detail = await backendApi.getHuddle(huddle.id);
    }
    if (detail.huddle.status !== "synthesized") {
      const synthesized = await backendApi.synthesizeHuddle(huddle.id);
      return mapHuddleDetail(detail, synthesized.brief);
    }
    return mapHuddleDetail(detail);
  },
};
