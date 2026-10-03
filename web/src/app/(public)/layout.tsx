import type { Metadata } from "next";
import type { ReactNode } from "react";

/**
 * Candidate-facing pages (ATS Phase E): no navigation, no session, not
 * indexed, and no Referer header, so the token in the URL is never sent to
 * another site.
 */
export const metadata: Metadata = {
  title: "Application status",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function PublicLayout({ children }: { children: ReactNode }) {
  return <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10 sm:px-6">{children}</main>;
}
