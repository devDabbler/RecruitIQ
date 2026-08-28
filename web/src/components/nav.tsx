"use client";

import Link from "next/link";
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
  { href: "/upload", label: "Resume Upload", icon: Upload },
  { href: "/assistant", label: "AI Assistant", icon: Bot },
] as const;

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
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            <span className="hidden lg:inline">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
