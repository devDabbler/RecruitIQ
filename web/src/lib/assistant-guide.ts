/**
 * What the assistant can and cannot answer, shown on the assistant page.
 *
 * Each "can" line maps to a tool in backend/services/assistant_tools.py; each
 * limit is something a visitor would otherwise discover by getting a polite
 * refusal. Keep this in step with the tool list: a guide that promises a
 * capability the tools lack is worse than no guide.
 */
export type GuideItem = { title: string; example: string };

export const ASSISTANT_CAN: GuideItem[] = [
  {
    title: "Find candidates by skill, role, or industry",
    example: "Python engineers with healthcare experience",
  },
  {
    title: "Narrow a search by place",
    example: "A city, a state, or a region like west coast",
  },
  {
    title: "Rank candidates for an open job",
    example: "Best fits for the Data Engineer role?",
  },
  {
    title: "Explain why someone fits a role",
    example: "Why is Elena Vasquez a good fit for the Senior Data Scientist role?",
  },
  {
    title: "Look up a profile, resume, or job",
    example: "What is on Marcus Bell's resume?",
  },
  {
    title: "Summarize the pipeline",
    example: "How many candidates are interviewing?",
  },
];

export const ASSISTANT_LIMITS: string[] = [
  "Only searches this demo database, not LinkedIn or the web.",
  "Read-only: it cannot change stages, edit records, send email, or schedule.",
  "Location is the only exact filter. Experience and education are matched by meaning.",
  "Salary lookups use a live source and may return no figures.",
  "Chats are saved in this browser only.",
];
