import { HuddleSchema, type Huddle } from "../types/huddle";
import { makeHuddle, completeHuddle } from "../data/demo";
export const isLive = process.env.NEXT_PUBLIC_API_MODE === "live";
const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(path: string, body: unknown): Promise<Huddle> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    const result = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!result.ok)
      throw new Error(
        `The service returned ${result.status}. Please retry or switch to the demo.`,
      );
    const parsed = HuddleSchema.safeParse(await result.json());
    if (!parsed.success)
      throw new Error(
        "The service response does not match the agreed huddle format.",
      );
    return parsed.data;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError")
      throw new Error(
        "The service took too long. Please retry or switch to the demo.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const huddleApi = {
  async create(question: string, forceDemo = false): Promise<Huddle> {
    if (!question.trim() || question.length > 2000)
      throw new Error("Enter a question between 1 and 2,000 characters.");
    return isLive && !forceDemo
      ? request("/huddles", { question })
      : makeHuddle(question.trim(), `demo-${crypto.randomUUID()}`);
  },
  async requestExpert(huddle: Huddle): Promise<Huddle> {
    return huddle.demo
      ? { ...huddle, status: "pending" }
      : request(`/huddles/${encodeURIComponent(huddle.id)}/request`, {});
  },
  async respond(huddle: Huddle, response: string): Promise<Huddle> {
    if (response.trim().length < 20 || response.length > 4000)
      throw new Error(
        "Please enter a response between 20 and 4,000 characters.",
      );
    return huddle.demo
      ? completeHuddle(huddle, response.trim())
      : request(`/huddles/${encodeURIComponent(huddle.id)}/response`, {
          response: response.trim(),
        });
  },
};
