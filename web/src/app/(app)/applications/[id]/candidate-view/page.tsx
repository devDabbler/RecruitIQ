import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PublicStatusView } from "@/components/public-status-view";
import { getApplication, getCandidateView } from "@/lib/data";

export const dynamic = "force-dynamic";

/** What the candidate sees at their status link, previewed by staff and the demo. */
export default async function CandidateViewPage({
  params,
}: PageProps<"/applications/[id]/candidate-view">) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [view, application] = await Promise.all([getCandidateView(id), getApplication(id)]);
  if (!view || !application) notFound();

  return (
    <>
      <Link
        href={`/candidates/${application.candidate_id}`}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Back to {application.candidate_name}
      </Link>
      <div className="mb-6 max-w-2xl rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Preview. This is exactly what the candidate sees at their status link. Nothing here comes
        from notes, feedback, or match scores.
      </div>
      <div className="max-w-2xl">
        <PublicStatusView status={view} />
      </div>
    </>
  );
}
