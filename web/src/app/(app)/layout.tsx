import type { ReactNode } from "react";
import Link from "next/link";
import { Suspense } from "react";

import { SessionBadge, SessionBadgeFallback } from "@/components/session-badge";
import { SessionSidebar } from "@/components/session-sidebar";
import { Sidebar } from "@/components/sidebar";
import { DEPLOYMENT_MODE } from "@/lib/config";
import { footerNote } from "@/lib/deployment";

/**
 * The staff app shell: header, session badge, sidebar, footer.
 *
 * Lives in the (app) route group rather than the root layout so the
 * candidate-facing /c/[token] page (the (public) group) renders without any
 * of it (ATS Phase E). Route groups do not change URLs.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="flex h-14 items-center gap-4 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              R
            </span>
            <span>RecruitIQ</span>
          </Link>
          {/* Suspended on purpose, and load-bearing for every `loading.tsx`:
              SessionBadge reads cookies() and calls /auth/me, and runtime
              data read directly in a layout blocks navigation with no
              fallback. Behind a boundary the shell paints immediately. */}
          <div className="ml-auto shrink-0">
            <Suspense fallback={<SessionBadgeFallback />}>
              <SessionBadge />
            </Suspense>
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Same reason as the badge: the role-filtered sidebar waits on
            /auth/me, so the unfiltered one stands in until it resolves. */}
        <Suspense fallback={<Sidebar role={null} />}>
          <SessionSidebar />
        </Suspense>

        <div className="flex min-w-0 flex-1 flex-col">
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">{children}</main>

          <footer className="border-t border-slate-200 bg-white">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-slate-500 sm:px-6">
              <span>{footerNote(DEPLOYMENT_MODE)}</span>
              <Link href="/docs" className="font-medium text-slate-700 hover:underline">
                API docs
              </Link>
            </div>
          </footer>
        </div>
      </div>
    </>
  );
}
