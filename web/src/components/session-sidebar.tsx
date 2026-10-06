import { Sidebar } from "@/components/sidebar";
import { getPendingFeedbackCount } from "@/lib/data";
import { getUser } from "@/lib/session";

/**
 * The sidebar for the signed-in role. Rendered inside Suspense by the layout.
 * Fetches the pending-feedback badge (Track 2 Phase 4) alongside the user; a
 * failed count only hides the badge.
 */
export async function SessionSidebar() {
  const [user, pendingFeedback] = await Promise.all([
    getUser(),
    getPendingFeedbackCount().catch(() => 0),
  ]);
  return <Sidebar role={user?.role ?? null} pendingFeedback={pendingFeedback} />;
}
