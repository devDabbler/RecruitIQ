import { Nav } from "@/components/nav";
import { getUser } from "@/lib/session";

/**
 * The nav, with the admin-only entries once the session is known.
 *
 * Rendered inside a `<Suspense fallback={<Nav />}>` in the layout, so the six
 * public links paint immediately and the admin link fills in when /auth/me
 * answers, the same arrangement `SessionBadge` uses. Awaiting the session in
 * the layout itself would block every route's `loading.tsx`.
 */
export async function SessionNav() {
  const user = await getUser();
  return <Nav admin={user?.role === "admin"} />;
}
