import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";

import "./globals.css";

// globals.css resolves the Tailwind font tokens from --font-sans; the variable
// name must match or every screen silently falls back to the browser stack.
const inter = Inter({ variable: "--font-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RecruitIQ",
  description: "AI-assisted applicant tracking, built by a recruiter.",
};

/**
 * The document only. The staff shell is app/(app)/layout.tsx; the
 * candidate-facing pages are app/(public) and render without it.
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
