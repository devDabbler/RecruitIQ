/**
 * Deployment mode (Fractal pilot, Track 1 #1).
 *
 * `public` is recruitiq.io: a visitor is signed in as the read-only demo
 * account automatically and the shell says so. `internal` is a company
 * install holding real candidates: nobody is signed in silently, every page
 * needs a staff session, and the copy stops talking about a demo.
 *
 * The backend holds the real gate (`DEPLOYMENT_MODE` in its environment:
 * no demo tokens, no anonymous reads). This module is the web app's mirror
 * of that setting, kept pure so the routing decision is unit-tested.
 */
import { INTRO_DATA_NOTE } from "./dashboard-intro";
import { isPublicPath } from "./public-paths";

export type DeploymentMode = "public" | "internal";

export function parseDeploymentMode(raw: string | undefined): DeploymentMode {
  const value = (raw ?? "").trim().toLowerCase();
  if (value === "internal") return "internal";
  if (value === "" || value === "public") return "public";
  throw new Error(`DEPLOYMENT_MODE must be "public" or "internal", got "${raw}"`);
}

/** What the proxy does with a request that arrived without a session cookie. */
export type AnonymousAction = "pass" | "mint-demo" | "login";

/**
 * Paths an internal install serves without a session: the sign-in page and
 * the route handlers behind it. Candidate status pages are open in both
 * modes (see public-paths.ts).
 */
const INTERNAL_OPEN_PREFIXES = ["/login", "/api/auth/"] as const;

export function anonymousAction(pathname: string, mode: DeploymentMode): AnonymousAction {
  if (isPublicPath(pathname)) return "pass";
  if (mode === "public") return "mint-demo";
  if (INTERNAL_OPEN_PREFIXES.some((prefix) => pathname.startsWith(prefix))) return "pass";
  return "login";
}

/** Where to send a signed-out visitor, remembering where they were going. */
export function loginPath(pathname: string, search = ""): string {
  const next = pathname + search;
  if (next === "/" || next === "") return "/login";
  return `/login?next=${encodeURIComponent(next)}`;
}

// --- copy that differs by mode (user-visible: no em dashes) ----------------

export function footerNote(mode: DeploymentMode): string {
  return mode === "internal"
    ? "Internal deployment. Candidate data here is confidential to the hiring team."
    : "RecruitIQ is a portfolio demo. Data is seeded and read-only.";
}

export function loginTitle(mode: DeploymentMode): string {
  return mode === "internal" ? "Sign in" : "Administrator sign-in";
}

export function loginIntro(mode: DeploymentMode): string {
  return mode === "internal"
    ? "Sign in with your staff account to open RecruitIQ."
    : "Visitors browse as the read-only demo automatically. Sign in to save candidates and change data.";
}

export function dashboardDataNote(mode: DeploymentMode): string {
  return mode === "internal"
    ? "Candidates here are real people. Treat what you see as confidential hiring data."
    : INTRO_DATA_NOTE;
}

export function signedOutLabel(mode: DeploymentMode): string {
  return mode === "internal" ? "Signed out" : "Read-only demo";
}
