"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  Briefcase,
  LayoutDashboard,
  Sparkles,
  Upload,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Exactly the eight screens from the spec (§6). Interviews and Tasks keep their
 * API routes and stay visible in /docs, but get no nav entry: a tight, finished
 * eight reads better than ten where two feel thin.
 */
const LINKS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/matching", label: "Matching", icon: Sparkles },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/assistant", label: "Assistant", icon: Bot },
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
    <nav className="flex items-center gap-1">
      {LINKS.map(({ href, label, icon: Icon }) => {
        // "/" would otherwise prefix-match every route and light up permanently.
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:bg-indigo-50 hover:text-indigo-700",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            <span className="hidden md:inline">{label}</span>
            <PendingDot />
          </Link>
        );
      })}
    </nav>
  );
}
