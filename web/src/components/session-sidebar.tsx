import { Sidebar } from "@/components/sidebar";
import { getUser } from "@/lib/session";

/** The sidebar for the signed-in role. Rendered inside Suspense by the layout. */
export async function SessionSidebar() {
  const user = await getUser();
  return <Sidebar role={user?.role ?? null} />;
}
