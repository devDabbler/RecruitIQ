"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  Briefcase,
  LayoutDashboard,
  Scale,
  Sparkles,
  Upload,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The eight screens from the spec (§6) plus Transparency, which joined the
 * public nav on 2026-09-28: it started admin-only, but a transparency page
 * that hides behind a login undercuts its own point, and everything it shows
 * about a candidate is already on the demo-visible screens. Interviews and
 * Tasks keep their API routes and stay visible in /docs, but get no nav
 * entry: a tight, finished set reads better than one where tabs feel thin.
 */
const LINKS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/matching", label: "Matching", icon: Sparkles },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/assistant", label: "Assistant", icon: Bot },
  { href: "/transparency", label: "Transparency", icon: Scale },
] as const;

/**
 * A dot that appears only if the click did not resolve straight away.
 *
 * With a `loading.tsx` on every route, Next prefetches each destination and
 * navigation commits instantly, so this normally never shows — `useLinkStatus`
 * skips the pending state entirely for a prefetched route. It covers the case
 * the docs call out: the very first click, before the prefetch queue has
 * reached that link. The 120ms animation delay means a fast navigation does not
 * flash it, and the element is always rendered at a fixed size so toggling it
 * cannot shift the nav.
 */
function PendingDot() {
  const { pending } = useLinkStatus();
  return <span aria-hidden className={cn("nav-hint", pending && "is-pending")} />;
}

export function Nav() {
  const pathname = usePathname();

  return (
    // Icons only, spread across the row, until lg; labels from lg up. The
    // label span is display:none when hidden, so aria-label is what names the
    // link for screen readers on small screens, and title gives a tooltip.
    <nav className="flex items-center justify-between gap-1 lg:justify-start">
      {LINKS.map(({ href, label, icon: Icon }) => {
        // "/" would otherwise prefix-match every route and light up permanently.
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-label={label}
            title={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-1 rounded-md px-2 py-2 text-sm font-medium transition-colors sm:gap-2 sm:px-3 xl:px-2.5",
              active
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:bg-indigo-50 hover:text-indigo-700",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            <span className="hidden lg:inline">{label}</span>
            <PendingDot />
          </Link>
        );
      })}
    </nav>
  );
}
