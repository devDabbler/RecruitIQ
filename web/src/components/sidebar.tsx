"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

import { isActive, visibleGroups } from "@/lib/nav";
import type { Role } from "@/lib/permissions";
import { cn } from "@/lib/utils";

/**
 * A dot that appears only if a click did not resolve straight away.
 *
 * With a `loading.tsx` on every route, Next prefetches each destination and
 * navigation commits instantly, so this normally never shows. It covers the
 * very first click, before the prefetch queue has reached that link; the
 * delay in globals.css keeps a fast navigation from flashing it.
 */
function PendingDot() {
  const { pending } = useLinkStatus();
  return <span aria-hidden className={cn("nav-hint", pending && "is-pending")} />;
}

/**
 * Grouped navigation (spec section 6): labelled groups from lg up, an
 * icon-only rail below. Every link carries aria-label and title because the
 * label text is display:none on the rail.
 *
 * `role` hides what a role cannot use. The layout renders this with
 * `role={null}` (everything) as the Suspense fallback and swaps in the
 * filtered list once the session resolves, so the shell never waits on
 * /auth/me.
 */
export function Sidebar({ role }: { role: Role | null }) {
  const pathname = usePathname();

  return (
    <aside className="sticky top-14 h-[calc(100vh-3.5rem)] w-14 shrink-0 overflow-y-auto border-r border-slate-200 bg-white lg:w-56">
      <nav aria-label="Main" className="flex flex-col gap-4 px-2 py-4 lg:px-3">
        {visibleGroups(role).map((group) => (
          <div key={group.label}>
            <p className="mb-1 hidden px-2 text-xs font-medium tracking-wide text-slate-400 uppercase lg:block">
              {group.label}
            </p>
            <ul className="space-y-0.5">
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href, pathname);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-label={label}
                      title={label}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center justify-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors lg:justify-start",
                        active
                          ? "bg-indigo-600 text-white"
                          : "text-slate-600 hover:bg-indigo-50 hover:text-indigo-700",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden />
                      <span className="hidden lg:inline">{label}</span>
                      <PendingDot />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
