import { Eye, ShieldCheck } from "lucide-react";

import { getUser } from "@/lib/session";

/**
 * Says which account the visitor is on and, for the demo role, that writes will
 * be refused. Honest labelling: the gate is `enforce_read_only` in the backend,
 * so the banner describes a real restriction rather than implying the UI is
 * enforcing one (spec §2).
 */
export async function SessionBadge() {
  const user = await getUser();

  if (!user) {
    return (
      <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
        Not signed in
      </span>
    );
  }

  const isDemo = user.role === "demo";
  const Icon = isDemo ? Eye : ShieldCheck;

  return (
    <span
      className={
        isDemo
          ? "flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
          : "flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
      }
      title={
        isDemo
          ? "Read-only demo account. The API refuses writes for this role."
          : `Signed in as ${user.email}`
      }
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {isDemo ? "Read-only demo" : "Admin"}
    </span>
  );
}
