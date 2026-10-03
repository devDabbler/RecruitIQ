/**
 * The app's navigation, grouped as spec section 6 lays it out.
 *
 * Later phases add screens by appending to a group here (Phase D puts
 * Reports at the top of Admin). `hiddenFor` hides an item from roles that
 * cannot use it; the API refuses them anyway, so this is courtesy.
 */
import {
  BarChart3,
  Bot,
  Briefcase,
  CalendarCheck,
  LayoutDashboard,
  Mail,
  Scale,
  Settings,
  Sparkles,
  Upload,
  UserCog,
  Users,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "./permissions";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  hiddenFor?: Role[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Hiring",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard, hiddenFor: ["interviewer"] },
      { href: "/jobs", label: "Jobs", icon: Briefcase },
      { href: "/candidates", label: "Candidates", icon: Users },
      { href: "/interviews", label: "Interviews", icon: CalendarCheck },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/matching", label: "Matching", icon: Sparkles, hiddenFor: ["interviewer"] },
      { href: "/upload", label: "Upload", icon: Upload, hiddenFor: ["interviewer"] },
      { href: "/assistant", label: "Assistant", icon: Bot, hiddenFor: ["interviewer"] },
      { href: "/transparency", label: "Transparency", icon: Scale },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/reports", label: "Reports", icon: BarChart3, hiddenFor: ["interviewer"] },
      { href: "/team", label: "Team", icon: UserCog, hiddenFor: ["interviewer"] },
      { href: "/email-templates", label: "Email templates", icon: Mail, hiddenFor: ["interviewer"] },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

/** The groups a role sees. Null while the session resolves: everything. */
export function visibleGroups(role: Role | null | undefined): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !role || !item.hiddenFor?.includes(role)),
  })).filter((group) => group.items.length > 0);
}

export function isActive(href: string, pathname: string): boolean {
  // "/" would otherwise prefix-match every route and light up permanently.
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
