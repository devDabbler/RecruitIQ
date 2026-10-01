import type { Metadata } from "next";
import Link from "next/link";
import { Geist_Mono, Inter } from "next/font/google";
import { Suspense } from "react";

import { Nav } from "@/components/nav";
import { SessionBadge, SessionBadgeFallback } from "@/components/session-badge";
import "./globals.css";

// globals.css resolves the Tailwind font tokens from --font-sans; the variable
// name must match or every screen silently falls back to the browser stack.
const inter = Inter({ variable: "--font-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RecruitIQ",
  description: "AI-assisted applicant tracking, built by a recruiter.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">
        <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
          {/* Two rows below xl (logo and account on top, nav full width
              underneath), one row from xl up. The labelled nav plus the badge
              need about 1200px; squeezed into one row they pushed the page
              into sideways scroll at every width under 1280. */}
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 px-4 sm:px-6 xl:h-16 xl:flex-nowrap xl:gap-x-4">
            <Link
              href="/"
              className="flex h-14 items-center gap-2 font-semibold tracking-tight xl:h-auto"
            >
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
                R
              </span>
              <span>RecruitIQ</span>
            </Link>
            <div className="order-last w-full pb-2 xl:order-none xl:w-auto xl:flex-1 xl:pb-0">
              <Nav />
            </div>
            {/* Suspended on purpose, and load-bearing for every `loading.tsx`
                in the app. `SessionBadge` reads `cookies()` and calls
                /auth/me; the loading.js docs are explicit that runtime data
                accessed directly in a layout gets no fallback and blocks the
                navigation until the layout finishes. Behind a boundary, the
                shell and the route's skeleton paint immediately and the badge
                fills in. */}
            <div className="ml-auto shrink-0">
              <Suspense fallback={<SessionBadgeFallback />}>
                <SessionBadge />
              </Suspense>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">{children}</main>

        <footer className="border-t border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-slate-500 sm:px-6">
            <span>RecruitIQ is a portfolio demo. Data is seeded and read-only.</span>
            <a href="/docs" className="font-medium text-slate-700 hover:underline">
              API docs
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
