import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { DEPLOYMENT_MODE } from "@/lib/config";
import { INTRO_SUMMARY, INTRO_TITLE, TOUR_STEPS } from "@/lib/dashboard-intro";
import { dashboardDataNote } from "@/lib/deployment";

/**
 * What RecruitIQ is and where to start, above the live numbers. Rendered on
 * the error path too: a visitor who lands while the API is down should still
 * learn what they are looking at.
 */
export function DashboardIntro() {
  return (
    <section
      aria-labelledby="dashboard-intro-title"
      className="mb-8 rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-white p-6 sm:p-8"
    >
      <h1
        id="dashboard-intro-title"
        className="text-3xl font-semibold tracking-tight text-slate-900"
      >
        {INTRO_TITLE}
      </h1>
      <p className="mt-2 max-w-3xl text-base text-slate-700">{INTRO_SUMMARY}</p>
      <p className="mt-2 text-sm text-slate-500">{dashboardDataNote(DEPLOYMENT_MODE)}</p>

      <h2 className="mt-6 mb-3 text-xs font-semibold tracking-wide text-slate-500 uppercase">
        Quick tour
      </h2>
      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TOUR_STEPS.map((step, index) => (
          <li key={step.href}>
            <Link
              href={step.href}
              className="group flex h-full flex-col rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50"
            >
              <span className="flex items-center gap-2 font-medium text-slate-900">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                  {index + 1}
                </span>
                {step.label}
                <ArrowRight
                  className="ml-auto h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-600"
                  aria-hidden
                />
              </span>
              <span className="mt-2 text-sm text-slate-600">{step.detail}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
