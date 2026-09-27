import { z } from "zod";

export const QuestionSchema = z.object({
  specialty: z.string(), condition: z.string(), topic: z.string(), intent: z.string(), question: z.string(),
});
export const EvidenceSchema = z.object({
  id: z.string(), title: z.string(), publisher: z.string(), type: z.string(), date: z.string().nullable(),
  snippet: z.string(), url: z.string().nullable(), citation: z.string().optional(), verified: z.boolean(),
  relevance: z.number().optional(), relevance_type: z.enum(["direct", "contextual"]).optional(),
  source_type: z.string().optional(), external_id: z.string().nullable().optional(),
});
export const ExpertSchema = z.object({
  id: z.string(), name: z.string(), initials: z.string(), specialty: z.string(), expertise: z.array(z.string()),
  match: z.number().min(0).max(100), demo: z.boolean(), title: z.string().optional(), availability: z.string().optional(),
  score_breakdown: z.record(z.string(), z.number()).optional(),
});
export const BriefSchema = z.object({
  evidence: z.array(z.string()), takeaways: z.array(z.string()), uncertainty: z.string(), synthesisLabel: z.string(),
  evidenceItems: z.array(z.object({ statement: z.string(), source_ids: z.array(z.string()), label: z.string() })).optional(),
  expertLabel: z.string().optional(), generatedBy: z.string().optional(), citations: z.array(z.string()).optional(),
});
export const HuddleSchema = z.object({
  id: z.string(), createdAt: z.string(), status: z.enum(["ready", "pending", "complete"]), question: QuestionSchema,
  sources: z.array(EvidenceSchema), expert: ExpertSchema.nullable(), response: z.string().nullable(),
  responseIsSimulated: z.boolean().optional(), brief: BriefSchema.nullable(), demo: z.boolean(),
});
export type ClinicalQuestion = z.infer<typeof QuestionSchema>;
export type Evidence = z.infer<typeof EvidenceSchema>;
export type Expert = z.infer<typeof ExpertSchema>;
export type Huddle = z.infer<typeof HuddleSchema>;
export type View = "home" | "understanding" | "evidence" | "expert" | "brief" | "graph";

export interface QuestionDTO extends ClinicalQuestion {
  question_id: string; key_context: string[]; extraction_method: string; confidence: number; phi_detected: boolean;
}
export interface EvidenceDTO {
  id: string; title: string; type?: string | null; source_type?: string | null; publisher: string;
  date: string | null; url: string | null; citation?: string; relevance?: number;
  relevance_type?: "direct" | "contextual"; verified: boolean;
  snippet?: string; full_text?: string; external_id?: string | null;
}
export interface ExpertDTO {
  id: string; name: string; title: string; specialty: string; expertise: string[]; match_score: number;
  availability: string; score_breakdown: Record<string, number>; is_demo: boolean;
}
export interface BriefDTO {
  question: string; evidence: { statement: string; source_ids: string[]; label: string }[];
  expert_perspective: { summary: string; expert_name: string; is_simulated: boolean; audio_url: string | null; label: string };
  key_takeaways: { point: string; source_ids: string[]; label: string }[]; uncertainty: string[];
  sources: { id: string; citation: string; url: string | null; verified: boolean }[];
  generated_by: string; disclaimer: string;
}
export interface HuddleDetailDTO {
  huddle: { id: string; question_id: string; expert_id: string; evidence_ids: string[]; status: "awaiting_expert" | "responded" | "synthesized"; created_at: string; updated_at: string };
  question: { specialty: string; condition: string; topic: string; intent: string; question: string };
  evidence: EvidenceDTO[]; expert: ExpertDTO; responses: { text: string; is_simulated: boolean }[];
  brief: BriefDTO | null; disclaimer: string;
}
export interface AnalyticsDTO {
  total: number; by_specialty: { name: string; count: number }[]; by_condition: { name: string; count: number }[];
  by_topic: { name: string; count: number }[]; by_intent: { name: string; count: number }[];
  unanswered: { topic: string; condition: string; count: number }[];
  emerging: { topic: string; last_7d: number; prior_7d: number; growth: number }[];
  timeseries: { date: string; count: number }[]; includes_seeded_data: boolean;
}

const initials = (name: string) => name.split(/\s+/).map((part) => part[0] || "").join("").slice(0, 2).toUpperCase();
export function mapHuddleDetail(dto: HuddleDetailDTO, brief: BriefDTO | null = dto.brief): Huddle {
  const status = dto.huddle.status === "synthesized" ? "complete" : dto.huddle.status === "responded" ? "pending" : "ready";
  const response = dto.responses.at(-1);
  return {
    id: dto.huddle.id, createdAt: dto.huddle.created_at, status,
    question: { specialty: dto.question.specialty, condition: dto.question.condition, topic: dto.question.topic, intent: dto.question.intent, question: dto.question.question },
    sources: dto.evidence.map((s) => ({ id: s.id, title: s.title, publisher: s.publisher, type: s.type || s.source_type || "Source", date: s.date ?? null, url: s.url ?? null, snippet: s.snippet || s.full_text || "", citation: s.citation, verified: s.verified, relevance: s.relevance, relevance_type: s.relevance_type, source_type: s.source_type || undefined, external_id: s.external_id })),
    expert: dto.expert ? { id: dto.expert.id, name: dto.expert.name, initials: initials(dto.expert.name), specialty: dto.expert.specialty,
      expertise: dto.expert.expertise, match: dto.expert.match_score, demo: dto.expert.is_demo, title: dto.expert.title,
      availability: dto.expert.availability, score_breakdown: dto.expert.score_breakdown } : null,
    response: response?.text ?? null, responseIsSimulated: response?.is_simulated ?? false,
    brief: brief ? { evidence: brief.evidence.map((item) => item.statement), evidenceItems: brief.evidence,
      takeaways: brief.key_takeaways.map((item) => item.point), uncertainty: brief.uncertainty.join("\n"),
      synthesisLabel: brief.disclaimer, generatedBy: brief.generated_by, expertLabel: brief.expert_perspective.label,
      citations: brief.sources.map((source) => source.id) } : null,
    demo: false,
  };
}
