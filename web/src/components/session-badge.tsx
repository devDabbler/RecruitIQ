import Link from "next/link";
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

  if (!user || user.role === "demo") {
    return (
      <span className="flex items-center gap-3">
        <span
          className="flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700"
          title="Read-only demo account. The API refuses writes for this role."
        >
          <Eye className="h-3.5 w-3.5" aria-hidden />
          Read-only demo
        </span>
        <Link
          href="/login"
          className="text-xs font-medium text-slate-500 hover:text-indigo-700"
        >
          Sign in
        </Link>
      </span>
    );
  }

  return (
    <span className="flex items-center gap-3">
      <span
        className="flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700"
        title={`Signed in as ${user.email}`}
      >
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
        Admin
      </span>
      <form action="/api/auth/logout" method="post">
        <button
          type="submit"
          className="text-xs font-medium text-slate-500 hover:text-indigo-700"
        >
          Sign out
        </button>
      </form>
    </span>
  );
}
