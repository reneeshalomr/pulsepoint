import { z } from "zod";
export const QuestionSchema = z.object({
  specialty: z.string(),
  condition: z.string(),
  topic: z.string(),
  intent: z.string(),
  question: z.string(),
});
export const EvidenceSchema = z.object({
  id: z.string(),
  title: z.string(),
  publisher: z.string(),
  type: z.string(),
  date: z.string(),
  snippet: z.string(),
  url: z
    .url()
    .refine(
      (url) => /^https?:\/\//.test(url),
      "Source URLs must use HTTP or HTTPS",
    ),
  verified: z.boolean(),
});
export const ExpertSchema = z.object({
  id: z.string(),
  name: z.string(),
  initials: z.string(),
  specialty: z.string(),
  expertise: z.array(z.string()),
  match: z.number().min(0).max(100),
  demo: z.boolean(),
});
export const BriefSchema = z.object({
  evidence: z.array(z.string()),
  takeaways: z.array(z.string()),
  uncertainty: z.string(),
  synthesisLabel: z.string(),
});
export const HuddleSchema = z.object({
  id: z.string(),
  createdAt: z.string(),
  status: z.enum(["ready", "pending", "complete"]),
  question: QuestionSchema,
  sources: z.array(EvidenceSchema),
  expert: ExpertSchema.nullable(),
  response: z.string().nullable(),
  brief: BriefSchema.nullable(),
  demo: z.boolean(),
});
export type ClinicalQuestion = z.infer<typeof QuestionSchema>;
export type Evidence = z.infer<typeof EvidenceSchema>;
export type Expert = z.infer<typeof ExpertSchema>;
export type Huddle = z.infer<typeof HuddleSchema>;
export type View =
  "home" | "understanding" | "evidence" | "expert" | "brief" | "graph";
