import type { Evidence, Expert, Huddle } from "../types/huddle";

export const EXAMPLE_QUESTION =
  "What evidence should I review about treatment sequencing in breast cancer, and which questions should I bring to an oncology expert?";
export const EXAMPLE_RESPONSE =
  "For this demo, I would frame the discussion around the treatment history, the specific clinical question, and which sources are current. The linked resources are starting points for review, not a patient-specific recommendation. I would ask the treating team to clarify missing context before discussing options.";

export const sources: Evidence[] = [
  {
    id: "nci-pdq",
    title: "Breast Cancer Treatment (PDQ®)",
    publisher: "National Cancer Institute",
    type: "Evidence summary",
    date: "Living resource · review current page",
    snippet:
      "A professional reference for reviewing breast cancer treatment evidence. This demo links to the source; it does not extract or validate treatment recommendations.",
    url: "https://www.cancer.gov/types/breast/hp/breast-treatment-pdq",
    verified: true,
  },
  {
    id: "nci-trials",
    title: "Cancer Clinical Trials Information",
    publisher: "National Cancer Institute",
    type: "Research resource",
    date: "Living resource · review current page",
    snippet:
      "Background on clinical trials and how to find studies. Trial availability and eligibility must be checked directly with the study team.",
    url: "https://www.cancer.gov/research/participate/clinical-trials",
    verified: true,
  },
  {
    id: "nci-breast",
    title: "Breast Cancer—Health Professional Version",
    publisher: "National Cancer Institute",
    type: "Clinical resource",
    date: "Living resource · review current page",
    snippet:
      "A starting point for breast cancer information and professional resources. Included as a curated demo link, not a live search result.",
    url: "https://www.cancer.gov/types/breast/hp",
    verified: true,
  },
];
export const expert: Expert = {
  id: "demo-maya",
  name: "Dr. Maya Patel",
  initials: "MP",
  specialty: "Oncology",
  expertise: ["Breast cancer", "Treatment sequencing", "Clinical trials"],
  match: 94,
  demo: true,
};

export function makeHuddle(question: string, id = "demo-huddle"): Huddle {
  const supported = /breast/i.test(question);
  return {
    id,
    createdAt: new Date().toISOString(),
    status: "ready",
    demo: true,
    question: {
      question,
      specialty: supported ? "Oncology" : "Needs review",
      condition: supported ? "Breast cancer" : "Not classified",
      topic: supported ? "Treatment sequencing" : "General question",
      intent: "Evidence review",
    },
    sources: supported ? sources : [],
    expert: supported ? expert : null,
    response: null,
    brief: null,
  };
}

export function completeHuddle(huddle: Huddle, response: string): Huddle {
  return {
    ...huddle,
    status: "complete",
    response,
    brief: {
      synthesisLabel: "Template-based demo synthesis · not clinical advice",
      evidence: huddle.sources.length
        ? [
            "The curated NCI links offer starting points for a literature review. No live retrieval or patient-specific evidence assessment has been performed.",
            "Open each source to check its current content, scope, and applicability before using it in a clinical discussion.",
          ]
        : [
            "No curated evidence matches this question in the demo. Evidence review remains incomplete.",
          ],
      takeaways: [
        "Keep the original question and missing clinical context visible.",
        "Review source material directly and check its currency.",
        "Treat the demo expert response as a discussion prompt, not a recommendation.",
      ],
      uncertainty:
        "Patient-specific context, source applicability, and the latest treatment updates have not been assessed. This prototype cannot determine a clinical course of action.",
    },
  };
}

export const initialHuddles: Huddle[] = [
  completeHuddle(
    {
      ...makeHuddle(EXAMPLE_QUESTION, "demo-001"),
      createdAt: "2026-09-25T13:00:00Z",
    },
    EXAMPLE_RESPONSE,
  ),
  {
    ...makeHuddle(
      "What resources can help prepare a breast cancer side-effect management discussion?",
      "demo-002",
    ),
    createdAt: "2026-09-25T11:00:00Z",
    status: "pending",
    question: {
      ...makeHuddle(EXAMPLE_QUESTION).question,
      question:
        "What resources can help prepare a breast cancer side-effect management discussion?",
      topic: "Side-effect management",
    },
  },
];

export const graphTopics = [
  { topic: "Treatment sequencing", count: 42 },
  { topic: "Side-effect management", count: 31 },
  { topic: "Clinical trials", count: 24 },
  { topic: "Access & coverage", count: 18 },
  { topic: "Biomarker testing", count: 13 },
];
